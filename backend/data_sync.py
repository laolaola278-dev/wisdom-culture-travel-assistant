import os
import json
import time
import hashlib
import threading
import pandas as pd
from config import Config


class DataSync:
    def __init__(self, data_cleaner, knowledge_graph, vector_store, rag_engine):
        self.data_cleaner = data_cleaner
        self.kg = knowledge_graph
        self.vector_store = vector_store
        self.rag_engine = rag_engine
        self.snapshot_path = os.path.join(Config.GRAPH_DATA_DIR, 'data_snapshot.json')
        self._last_snapshot = {}
        self._running = False
        self._thread = None

    def check_for_updates(self):
        current_snapshot = self._take_snapshot()
        if not self._last_snapshot:
            self._last_snapshot = current_snapshot
            self._load_snapshot()
            return False

        changed_files = []
        for fpath, mtime in current_snapshot.items():
            if self._last_snapshot.get(fpath) != mtime:
                changed_files.append(fpath)

        if changed_files:
            print(f"[DataSync] 检测到 {len(changed_files)} 个文件变更:")
            for f in changed_files:
                print(f"  - {os.path.basename(f)}")
            self._last_snapshot = current_snapshot
            self._save_snapshot()
            return True
        return False

    def sync(self, force=False):
        if force or self.check_for_updates():
            print("[DataSync] 开始增量同步...")
            self.data_cleaner.load_all_data()

            old_nodes = self.kg.graph.number_of_nodes()
            self.kg.build_from_data(self.data_cleaner)
            new_nodes = self.kg.graph.number_of_nodes()

            all_segments = self.data_cleaner.get_all_text_segments()
            if self.vector_store:
                added = self.vector_store.incremental_update(all_segments)
                print(f"[DataSync] 向量索引更新: +{added} 条")

            self.rag_engine.text_segments = all_segments
            for i, seg in enumerate(all_segments):
                self.rag_engine.segment_index[i] = seg

            print(f"[DataSync] 同步完成: 图谱 {old_nodes}→{new_nodes} 节点")
            return True
        return False

    def start_auto_sync(self, interval_hours=None):
        if self._running:
            return
        self._running = True
        interval = interval_hours or Config.DATA_SYNC_INTERVAL_HOURS
        self._thread = threading.Thread(
            target=self._sync_loop,
            args=(interval,),
            daemon=True
        )
        self._thread.start()
        print(f"[DataSync] 自动同步已启动 (每 {interval} 小时)")

    def stop(self):
        self._running = False

    def _sync_loop(self, interval_hours):
        while self._running:
            time.sleep(interval_hours * 3600)
            try:
                self.sync(force=False)
            except Exception as e:
                print(f"[DataSync] 同步异常: {e}")

    def _take_snapshot(self):
        snapshot = {}
        if not os.path.exists(Config.DATA_DIR):
            return snapshot
        for f in os.listdir(Config.DATA_DIR):
            if f.endswith('.xlsx'):
                fpath = os.path.join(Config.DATA_DIR, f)
                try:
                    snapshot[fpath] = os.path.getmtime(fpath)
                except OSError:
                    pass
        return snapshot

    def _save_snapshot(self):
        try:
            with open(self.snapshot_path, 'w') as f:
                json.dump(self._last_snapshot, f, indent=2)
        except Exception as e:
            print(f"[DataSync] 快照保存失败: {e}")

    def _load_snapshot(self):
        if os.path.exists(self.snapshot_path):
            try:
                with open(self.snapshot_path) as f:
                    self._last_snapshot = json.load(f)
            except Exception:
                self._last_snapshot = {}

    def get_sync_status(self):
        return {
            "enabled": Config.DATA_SYNC_ENABLED,
            "interval_hours": Config.DATA_SYNC_INTERVAL_HOURS,
            "running": self._running,
            "tracked_files": len(self._last_snapshot),
        }
