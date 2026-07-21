import uuid
import time
import threading
from collections import defaultdict, OrderedDict
from config import Config


class UserSession:
    def __init__(self, session_id=None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.queries = []
        self.interested_entities = []
        self.interested_types = defaultdict(int)
        self.created_at = time.time()
        self.last_active = time.time()
        self.preferences = {}

    def record_query(self, question, entities=None, agent=None):
        self.queries.append({
            "question": question,
            "entities": entities or [],
            "agent": agent,
            "timestamp": time.time(),
        })
        if entities:
            for e in entities:
                if isinstance(e, dict):
                    name = e.get('name', '')
                    etype = e.get('type', '')
                    if name and name not in [x['name'] for x in self.interested_entities]:
                        self.interested_entities.append({"name": name, "type": etype})
                        self.interested_types[etype] += 1
        self.last_active = time.time()

    def infer_preferences(self):
        if self.interested_types:
            top_type = max(self.interested_types, key=self.interested_types.get)
            self.preferences['favorite_type'] = top_type
        visited_names = [e['name'] for e in self.interested_entities]
        self.preferences['visited_entities'] = visited_names
        return self.preferences

    def get_recent_queries(self, n=5):
        return [q['question'] for q in self.queries[-n:]]

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "query_count": len(self.queries),
            "interested_types": dict(self.interested_types),
            "interested_entities": self.interested_entities[-8:],
            "preferences": self.preferences,
            "recent_queries": self.get_recent_queries(3),
            "last_active": self.last_active,
        }


class SessionManager:
    def __init__(self, kg, max_sessions=1000, ttl_seconds=3600):
        self.kg = kg
        self.sessions = OrderedDict()
        self.max_sessions = max_sessions
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def get_or_create(self, session_id=None):
        with self._lock:
            if session_id and session_id in self.sessions:
                self.sessions[session_id].last_active = time.time()
                self.sessions.move_to_end(session_id)
                return self.sessions[session_id]
            if len(self.sessions) >= self.max_sessions:
                self.sessions.popitem(last=False)
            session = UserSession(session_id)
            self.sessions[session.session_id] = session
            return session

    def record(self, session_id, question, entities=None, agent=None):
        session = self.get_or_create(session_id)
        session.record_query(question, entities, agent)
        return session

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def _cleanup_loop(self):
        while True:
            time.sleep(300)
            self._cleanup()

    def _cleanup(self):
        with self._lock:
            now = time.time()
            expired = [
                sid for sid, sess in self.sessions.items()
                if now - sess.last_active > self.ttl
            ]
            for sid in expired:
                del self.sessions[sid]

    def get_stats(self):
        return {
            "active_sessions": len(self.sessions),
            "max_sessions": self.max_sessions,
            "session_ttl_seconds": self.ttl,
        }


class RecommendationEngine:
    def __init__(self, kg, data_cleaner, session_manager):
        self.kg = kg
        self.data_cleaner = data_cleaner
        self.session_manager = session_manager

    def recommend_for_user(self, session_id, top_k=5):
        session = self.session_manager.get_session(session_id)
        if not session or not session.interested_entities:
            return self._default_recommendations(top_k)

        prefs = session.infer_preferences()
        recommended = []
        seen = {e['name'] for e in session.interested_entities}

        for entity in session.interested_entities[-3:]:
            try:
                nearby = self.kg.find_nearby_entities(entity['name'], max_depth=2)
                for n in nearby:
                    if n['name'] not in seen and len(recommended) < top_k:
                        seen.add(n['name'])
                        recommended.append({
                            "name": n['name'],
                            "type": n['type'],
                            "reason": f"与您感兴趣的{entity['name']}相关联",
                            "depth": n.get('depth', 0),
                        })
            except Exception:
                continue

        if len(recommended) < top_k:
            pref_type = prefs.get('favorite_type', '')
            if pref_type:
                for n in self.kg.graph.nodes():
                    if len(recommended) >= top_k:
                        break
                    ntype = self.kg.graph.nodes[n].get('type', '')
                    if ntype == pref_type and n not in seen:
                        recommended.append({
                            "name": n,
                            "type": ntype,
                            "reason": f"基于您对{pref_type}的兴趣推荐",
                            "depth": 0,
                        })
                        seen.add(n)

        if not recommended:
            return self._default_recommendations(top_k)
        return recommended[:top_k]

    def _default_recommendations(self, top_k):
        hot_types = ['景点', '非遗项目', '公园', '图书馆']
        recommended = []
        seen = set()
        for t in hot_types:
            for n in self.kg.graph.nodes():
                if len(recommended) >= top_k:
                    break
                ntype = self.kg.graph.nodes[n].get('type', '')
                if ntype == t and n not in seen:
                    recommended.append({
                        "name": n,
                        "type": ntype,
                        "reason": f"热门{ntype}推荐",
                        "depth": 0,
                    })
                    seen.add(n)
        return recommended[:top_k]
