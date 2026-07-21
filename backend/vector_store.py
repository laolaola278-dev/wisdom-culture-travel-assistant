import os
import json
import pickle
import hashlib
import threading
import numpy as np
from config import Config


class VectorStore:
    def __init__(self):
        self.dimension = 256
        self.vectors = np.empty((0, self.dimension), dtype=np.float32)
        self.segments = []
        self.index_map = {}
        self.cache_path = os.path.join(Config.GRAPH_DATA_DIR, 'vector_index.pkl')
        self._backend = None
        self._model = None
        self._init_backend()

    def _init_backend(self):
        model_loaded = False
        model_name = Config.EMBEDDING_MODEL
        if model_name:
            try:
                import huggingface_hub
                import sentence_transformers
                cache_dir = Config.MODEL_CACHE_DIR
                os.makedirs(cache_dir, exist_ok=True)

                result = [None]
                error = [None]

                def _load():
                    try:
                        from sentence_transformers import SentenceTransformer
                        result[0] = SentenceTransformer(
                            model_name, device='cpu', cache_folder=cache_dir
                        )
                    except Exception as e:
                        error[0] = e

                t = threading.Thread(target=_load, daemon=True)
                t.start()
                t.join(timeout=30)

                if result[0] is not None:
                    self._model = result[0]
                    self.dimension = self._model.get_sentence_embedding_dimension()
                    self.vectors = np.empty((0, self.dimension), dtype=np.float32)
                    self._backend = 'sentence-transformers'
                    model_loaded = True
                    print(f"[VectorStore] 已加载嵌入模型: {model_name} (dim={self.dimension})")
                elif error[0] is not None:
                    print(f"[VectorStore] 模型加载失败: {error[0]}")
            except ImportError:
                print("[VectorStore] sentence-transformers 未安装")
        else:
            print("[VectorStore] EMBEDDING_MODEL 为空，跳过模型下载")

        if not model_loaded:
            self._init_tfidf_fallback()

    def _init_tfidf_fallback(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._backend = 'tfidf'
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=self.dimension, analyzer='char', ngram_range=(1, 2)
            )
            self._tfidf_matrix = None
            self._tfidf_fitted = False
            print(f"[VectorStore] 使用 TF-IDF 降级模式 (dim={self.dimension})")
        except ImportError:
            print("[VectorStore] sklearn 未安装，向量搜索不可用")
            self._backend = 'none'

    def _encode(self, texts):
        if self._backend == 'sentence-transformers' and self._model is not None:
            return self._model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
        if self._backend == 'tfidf' and hasattr(self, '_tfidf_vectorizer'):
            if not self._tfidf_fitted:
                self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(texts)
                self._tfidf_fitted = True
            else:
                self._tfidf_matrix = self._tfidf_vectorizer.transform(texts)
            arr = self._tfidf_matrix.toarray().astype(np.float32)
            # L2 归一化，使点积等价于余弦相似度
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1
            return arr / norms
        raise RuntimeError("No embedding backend available")

    def build_index(self, text_segments):
        if not text_segments:
            self.segments = []
            self.vectors = np.empty((0, self.dimension), dtype=np.float32)
            return

        texts = [s['text'] for s in text_segments]
        self.segments = text_segments

        try:
            embeddings = self._encode(texts)
            if embeddings is None or (hasattr(embeddings, 'shape') and embeddings.shape[0] == 0):
                print("[VectorStore] 编码结果为空")
                self.vectors = np.empty((0, self.dimension), dtype=np.float32)
                return
            self.vectors = np.array(embeddings, dtype=np.float32)
            actual_dim = self.vectors.shape[1]
            if actual_dim != self.dimension:
                self.dimension = actual_dim
        except Exception as e:
            print(f"[VectorStore] 编码失败: {e}")
            self.vectors = np.empty((0, self.dimension), dtype=np.float32)
            return

        for i, seg in enumerate(text_segments):
            content_hash = hashlib.md5(seg['text'].encode()).hexdigest()
            self.index_map[content_hash] = i

        self._save_cache()
        print(f"[VectorStore] 索引构建完成: {len(self.segments)}条, dim={self.dimension}")

    def search(self, query, top_k=10):
        if len(self.segments) == 0 or self.vectors.shape[0] == 0:
            return []
        if self._backend == 'none':
            return []

        try:
            query_vec = self._encode([query])[0]
        except Exception as e:
            print(f"[VectorStore] 查询编码失败: {e}")
            return []

        query_vec = np.array(query_vec, dtype=np.float32).reshape(1, -1)
        vectors = self.vectors
        if vectors.shape[1] != query_vec.shape[1]:
            if vectors.size == 0:
                return []
            # 仅对本次比较做局部截断，不得改写 self.vectors（破坏性且并发不安全）
            min_dim = min(vectors.shape[1], query_vec.shape[1])
            vectors = vectors[:, :min_dim]
            query_vec = query_vec[:, :min_dim]

        similarities = np.dot(vectors, query_vec.T).flatten()

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if similarities[idx] > Config.VECTOR_SIMILARITY_THRESHOLD:
                results.append({
                    "segment": self.segments[idx],
                    "score": float(similarities[idx]),
                    "rank": len(results) + 1
                })
        return results

    def incremental_update(self, new_segments):
        if not new_segments:
            return 0

        existing_hashes = set(self.index_map.keys())
        truly_new = []
        for seg in new_segments:
            h = hashlib.md5(seg['text'].encode()).hexdigest()
            if h not in existing_hashes:
                truly_new.append(seg)

        if not truly_new:
            return 0

        old_len = len(self.segments)
        self.segments.extend(truly_new)
        try:
            new_vecs = self._encode([s['text'] for s in truly_new])
            new_vecs = np.array(new_vecs, dtype=np.float32)
            if new_vecs.shape[1] != self.vectors.shape[1] and self.vectors.size > 0:
                # 维度不一致说明编码后端已变更：跨空间向量不可比，
                # 拒绝混入（与 load_cache 的后端一致性策略统一），等待全量重建
                print(f"[VectorStore] 增量向量维度 {new_vecs.shape[1]} 与索引 {self.vectors.shape[1]} 不一致，跳过本次增量")
                self.segments = self.segments[:old_len]
                return 0
            self.vectors = np.vstack([self.vectors, new_vecs]) if self.vectors.size else new_vecs
        except Exception as e:
            print(f"[VectorStore] 增量更新编码失败: {e}")
            self.segments = self.segments[:old_len]
            return 0

        for i, seg in enumerate(truly_new):
            h = hashlib.md5(seg['text'].encode()).hexdigest()
            self.index_map[h] = old_len + i

        self._save_cache()
        return len(truly_new)

    def _save_cache(self):
        try:
            if self.vectors.size == 0:
                return
            data = {
                'vectors': self.vectors.tobytes(),
                'vector_shape': self.vectors.shape,
                'vector_dtype': str(self.vectors.dtype),
                'segments': self.segments,
                'index_map': self.index_map,
                'dimension': self.dimension,
                'backend': self._backend,
            }
            if self._backend == 'tfidf' and hasattr(self, '_tfidf_vectorizer'):
                data['tfidf_vectorizer'] = self._tfidf_vectorizer
                data['tfidf_fitted'] = self._tfidf_fitted
            with open(self.cache_path, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(f"[VectorStore] 缓存保存失败: {e}")

    def load_cache(self):
        if not os.path.exists(self.cache_path):
            return False
        try:
            with open(self.cache_path, 'rb') as f:
                data = pickle.load(f)
            self.vectors = np.frombuffer(data['vectors'], dtype=np.dtype(data['vector_dtype']))
            self.vectors = self.vectors.reshape(data['vector_shape'])
            self.segments = data['segments']
            self.index_map = data['index_map']
            self.dimension = data.get('dimension', self.vectors.shape[1])
            cached_backend = data.get('backend', 'cached')
            # 模型对象无法被 pickle，需要根据缓存后端重新初始化编码器
            if cached_backend == 'sentence-transformers':
                # __init__ 已加载过模型；可用则直接复用，避免重复加载
                if not (self._backend == 'sentence-transformers' and self._model is not None):
                    # 当前后端与缓存后端不一致（模型加载失败降级 TF-IDF 等）：
                    # 缓存向量与查询向量来自不同语义空间，比较无意义——丢弃缓存重建
                    print("[VectorStore] 缓存后端(sentence-transformers)与当前后端不一致，丢弃缓存")
                    self.vectors = np.empty((0, self.dimension), dtype=np.float32)
                    self.segments = []
                    self.index_map = {}
                    return False
            elif cached_backend == 'tfidf':
                if self._backend != 'tfidf':
                    print("[VectorStore] 缓存后端(tfidf)与当前后端不一致，丢弃缓存")
                    self.vectors = np.empty((0, self.dimension), dtype=np.float32)
                    self.segments = []
                    self.index_map = {}
                    return False
                if 'tfidf_vectorizer' in data:
                    self._tfidf_vectorizer = data['tfidf_vectorizer']
                    self._tfidf_fitted = data.get('tfidf_fitted', True)
                elif not hasattr(self, '_tfidf_vectorizer'):
                    self._init_tfidf_fallback()
            else:
                self._backend = cached_backend
            print(f"[VectorStore] 已加载缓存: {len(self.segments)}条, dim={self.dimension}, backend={self._backend}")
            return True
        except Exception as e:
            print(f"[VectorStore] 缓存加载失败: {e}")
            return False

    def get_stats(self):
        return {
            "total_segments": len(self.segments),
            "vector_dimension": self.dimension,
            "embedding_model": Config.EMBEDDING_MODEL,
            "backend": self._backend or 'none',
        }
