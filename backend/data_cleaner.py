import os
import json
import pandas as pd
import jieba
import jieba.analyse
import networkx as nx
from config import Config


class DataCleaner:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or Config.DATA_DIR
        self.data_cache = {}

    def load_all_data(self):
        if not os.path.exists(self.data_dir):
            print(f"数据目录不存在: {self.data_dir}")
            return {}
        files = [f for f in os.listdir(self.data_dir) if f.endswith('.xlsx')]
        for f in files:
            key = f.replace('.xlsx', '').replace('广州市白云区', '')
            path = os.path.join(self.data_dir, f)
            try:
                df = pd.read_excel(path)
                df = df.fillna('')
                self.data_cache[key] = df
                print(f"已加载: {key} ({len(df)}条记录)")
            except Exception as e:
                print(f"加载失败 {f}: {e}")
        return self.data_cache

    def get_scenic_spots(self):
        df = self.data_cache.get('A级景区名录')
        if df is not None:
            return df[['名称', '类型', '地址', '所在街镇']].to_dict('records')
        df2 = self.data_cache.get('旅游景点')
        if df2 is not None:
            return df2[['名称', '开放时间', '地址', '电话']].to_dict('records')
        return []

    def get_parks(self):
        df = self.data_cache.get('公园地点')
        if df is not None:
            return df[['名称', '开放时间', '地址', '简介或备注']].to_dict('records')
        return []

    def get_libraries(self):
        df = self.data_cache.get('图书馆分馆表')
        if df is not None:
            return df[['图书馆', '地址', '开放时间', '开放时间点']].to_dict('records')
        return []

    def get_library_activities(self):
        df = self.data_cache.get('图书馆活动信息表')
        if df is not None:
            cols = ['活动名称', '活动类别', '活动地点', '活动开始时间', '活动结束时间',
                    '活动简介', '活动名额', '活动状态', '分馆名称']
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].to_dict('records')
        return []

    def get_hotels(self):
        df = self.data_cache.get('星级酒店名录')
        if df is not None:
            return df[['名称', '类型', '地址', '所在镇街']].to_dict('records')
        return []

    def get_hostels(self):
        df = self.data_cache.get('旅馆业花名册')
        if df is not None:
            cols = ['现外挂酒店招牌名称', '经营地址', '所属镇街']
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].to_dict('records')
        return []

    def get_homestays(self):
        df = self.data_cache.get('民宿名录')
        if df is not None:
            return df[['名称', '类型', '地址', '所在街镇']].to_dict('records')
        return []

    def get_travel_agencies(self):
        df = self.data_cache.get('旅行社名录')
        if df is not None:
            return df[['名称', '地址']].to_dict('records')
        return []

    def get_charging_stations(self):
        df = self.data_cache.get('电动汽车充电站')
        if df is not None:
            return df[['企业（单位）名称', '地址', '镇街']].to_dict('records')
        return []

    def get_culture_stations(self):
        df = self.data_cache.get('镇街文化站名录')
        if df is not None:
            cols = ['名称', '详细地址', '开放时间', '文化站级别', '主管单位']
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].to_dict('records')
        return []

    def get_intangible_heritage(self):
        df = self.data_cache.get('非物质文化遗产代表性项目名录')
        if df is not None:
            cols = ['项目名称', '类别', '级别', '申报地区或单位', '项目保护单位', '公布时间']
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].to_dict('records')
        return []

    def get_archive_info(self):
        df = self.data_cache.get('国家档案馆查档指引')
        if df is not None:
            return df.to_dict('records')
        return []

    def get_power_stations(self):
        df = self.data_cache.get('供电局电网营业网点')
        if df is not None:
            cols = ['营业网点', '地址', '营业时间']
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].to_dict('records')
        return []

    def get_library_service_points(self):
        df = self.data_cache.get('图书馆服务点信息表')
        if df is not None:
            cols = ['服务点名称', '地址', '服务电话', '开放时间']
            available_cols = [c for c in cols if c in df.columns]
            return df[available_cols].to_dict('records')
        return []

    def get_youth_palace(self):
        df = self.data_cache.get('少年宫、业余体校')
        if df is not None:
            return df.to_dict('records')
        return []

    def get_all_text_segments(self):
        segments = []
        for item in self.get_scenic_spots():
            text = f"景区: {item.get('名称', '')}, 类型: {item.get('类型', '')}, 地址: {item.get('地址', '')}, 所在街镇: {item.get('所在街镇', '')}"
            segments.append({"text": text, "category": "景区", "name": item.get('名称', '')})

        for item in self.get_parks():
            text = f"公园: {item.get('名称', '')}, 地址: {item.get('地址', '')}, 开放时间: {item.get('开放时间', '')}, 简介: {item.get('简介或备注', '')}"
            segments.append({"text": text, "category": "公园", "name": item.get('名称', '')})

        for item in self.get_libraries():
            text = f"图书馆: {item.get('图书馆', '')}, 地址: {item.get('地址', '')}, 开放时间: {item.get('开放时间', '')} {item.get('开放时间点', '')}"
            segments.append({"text": text, "category": "图书馆", "name": item.get('图书馆', '')})

        for item in self.get_intangible_heritage():
            text = f"非遗项目: {item.get('项目名称', '')}, 类别: {item.get('类别', '')}, 级别: {item.get('级别', '')}, 申报地区: {item.get('申报地区或单位', '')}, 保护单位: {item.get('项目保护单位', '')}, 公布时间: {item.get('公布时间', '')}"
            segments.append({"text": text, "category": "非遗", "name": item.get('项目名称', '')})

        for item in self.get_hotels():
            text = f"星级酒店: {item.get('名称', '')}, 类型: {item.get('类型', '')}, 地址: {item.get('地址', '')}, 所在镇街: {item.get('所在镇街', '')}"
            segments.append({"text": text, "category": "酒店", "name": item.get('名称', '')})

        for item in self.get_homestays():
            text = f"民宿: {item.get('名称', '')}, 类型: {item.get('类型', '')}, 地址: {item.get('地址', '')}, 所在街镇: {item.get('所在街镇', '')}"
            segments.append({"text": text, "category": "民宿", "name": item.get('名称', '')})

        for item in self.get_travel_agencies():
            text = f"旅行社: {item.get('名称', '')}, 地址: {item.get('地址', '')}"
            segments.append({"text": text, "category": "旅行社", "name": item.get('名称', '')})

        for item in self.get_culture_stations():
            text = f"文化站: {item.get('名称', '')}, 地址: {item.get('详细地址', '')}, 开放时间: {item.get('开放时间', '')}, 级别: {item.get('文化站级别', '')}"
            segments.append({"text": text, "category": "文化站", "name": item.get('名称', '')})

        for item in self.get_charging_stations()[:200]:
            text = f"充电站: {item.get('企业（单位）名称', '')}, 地址: {item.get('地址', '')}, 镇街: {item.get('镇街', '')}"
            segments.append({"text": text, "category": "充电站", "name": item.get('企业（单位）名称', '')})

        for item in self.get_library_activities()[:300]:
            text = f"图书馆活动: {item.get('活动名称', '')}, 类别: {item.get('活动类别', '')}, 地点: {item.get('活动地点', '')}, 时间: {item.get('活动开始时间', '')}, 简介: {item.get('活动简介', '')}"
            segments.append({"text": text, "category": "活动", "name": item.get('活动名称', '')})

        for item in self.get_hostels()[:200]:
            text = f"旅馆: {item.get('现外挂酒店招牌名称', '')}, 地址: {item.get('经营地址', '')}, 所属镇街: {item.get('所属镇街', '')}"
            segments.append({"text": text, "category": "旅馆", "name": item.get('现外挂酒店招牌名称', '')})

        for item in self.get_power_stations():
            text = f"供电营业网点: {item.get('营业网点', '')}, 地址: {item.get('地址', '')}, 营业时间: {item.get('营业时间', '')}"
            segments.append({"text": text, "category": "供电", "name": item.get('营业网点', '')})

        for item in self.get_library_service_points():
            text = f"图书馆服务点: {item.get('服务点名称', '')}, 地址: {item.get('地址', '')}, 电话: {item.get('服务电话', '')}, 开放时间: {item.get('开放时间', '')}"
            segments.append({"text": text, "category": "服务点", "name": item.get('服务点名称', '')})

        return segments
