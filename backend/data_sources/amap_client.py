import requests
import json
import time
from config import Config


class AmapPOIClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or Config.AMAP_KEY
        self.base_url = "https://restapi.amap.com/v3"
        self._cache = {}
        self._cache_ttl = 86400

    def search_poi(self, keywords, city="广州", types=None, offset=20):
        cache_key = f"poi:{keywords}:{city}:{types}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        params = {
            "key": self.api_key,
            "keywords": keywords,
            "city": city,
            "offset": offset,
            "extensions": "all",
            "output": "JSON",
        }
        if types:
            params["types"] = types

        try:
            resp = requests.get(
                f"{self.base_url}/place/text",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "1" and data.get("count", "0") != "0":
                    pois = data.get("pois", [])
                    result = self._parse_pois(pois)
                    self._set_cache(cache_key, result)
                    return result
        except Exception as e:
            print(f"[AmapPOI] 搜索失败: {e}")
        return []

    def search_nearby(self, longitude, latitude, radius=1000, types=None):
        cache_key = f"nearby:{longitude}:{latitude}:{radius}:{types}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        params = {
            "key": self.api_key,
            "location": f"{longitude},{latitude}",
            "radius": radius,
            "offset": 20,
            "extensions": "all",
            "output": "JSON",
        }
        if types:
            params["types"] = types

        try:
            resp = requests.get(
                f"{self.base_url}/place/around",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "1":
                    pois = data.get("pois", [])
                    result = self._parse_pois(pois)
                    self._set_cache(cache_key, result)
                    return result
        except Exception as e:
            print(f"[AmapPOI] 附近搜索失败: {e}")
        return []

    def get_weather(self, city="440111"):
        cache_key = f"weather:{city}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        params = {
            "key": self.api_key,
            "city": city,
            "extensions": "all",
            "output": "JSON",
        }
        try:
            resp = requests.get(
                f"{self.base_url}/weather/weatherInfo",
                params=params,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "1":
                    result = data.get("lives", [{}])[0] if data.get("lives") else {}
                    self._set_cache(cache_key, result, ttl=3600)
                    return result
        except Exception as e:
            print(f"[AmapPOI] 天气查询失败: {e}")
        return {}

    def _parse_pois(self, pois):
        results = []
        for poi in pois:
            location = poi.get("location", "")
            lng, lat = "", ""
            if location and "," in location:
                lng, lat = location.split(",")
            results.append({
                "name": poi.get("name", ""),
                "type": poi.get("type", ""),
                "typecode": poi.get("typecode", ""),
                "address": poi.get("address", ""),
                "lng": float(lng) if lng else None,
                "lat": float(lat) if lat else None,
                "tel": poi.get("tel", ""),
                "distance": poi.get("distance", ""),
                "business_area": poi.get("business_area", ""),
                "rating": poi.get("biz_ext", {}).get("rating", ""),
                "cost": poi.get("biz_ext", {}).get("cost", ""),
            })
        return results

    def _get_cache(self, key):
        entry = self._cache.get(key)
        if entry and time.time() - entry['time'] < entry.get('ttl', self._cache_ttl):
            return entry['data']
        # 惰性清理过期条目，避免字典无界增长
        if entry:
            self._cache.pop(key, None)
        return None

    def _set_cache(self, key, data, ttl=None):
        # 上限保护：超限时先剔除最旧的条目
        if len(self._cache) >= 1000:
            oldest = min(self._cache, key=lambda k: self._cache[k]['time'])
            self._cache.pop(oldest, None)
        self._cache[key] = {
            'data': data,
            'time': time.time(),
        }
        if ttl:
            self._cache[key]['ttl'] = ttl

    def clear_cache(self):
        self._cache.clear()
