import json
import time

import requests

import threading
from queue import Queue

import os

class LocalRecord:
    normal_filename = 'normal.json'
    failed_filename = 'failed.json'
    normal = None
    failed = None

    def open(self):
        if os.path.exists(self.normal_filename):
            with open(self.normal_filename, 'r', encoding='utf-8') as f:
                self.normal = json.load(f)
        else:
            self.normal = {}

        if os.path.exists(self.failed_filename):
            with open(self.failed_filename, 'r', encoding='utf-8') as f:
                self.failed = json.load(f)
        else:
            self.failed = {}

    def save(self):
        with open(self.normal_filename, 'w', encoding='utf-8') as f:
            json.dump(self.normal, f, ensure_ascii=False, indent=4)
        with open(self.failed_filename, 'w', encoding='utf-8') as f:
            json.dump(self.failed, f, ensure_ascii=False, indent=4)

    def exist_by_id(self, id):
        return id in self.normal

    def add_by_id(self, id, data):
        self.normal[id] = data

    def add_failed_by_id(self, id, data):
        self.failed[id] = data


local_record = LocalRecord()


class AwemeItem:
    # # user
    # uid = 0
    # nickname = None
    #
    # # aweme_info
    # aweme_id = 0
    # create_time = 0
    # duration = 0
    # desc = None
    #
    # # url
    # share_url = None
    data = None
    desc = None
    aweme_id = None

    def __init__(self, data):
        self.data = {
            'author': {
                'uid': data['author']['uid'],
                'nickname': data['author']['nickname']
            },
            'aweme': {
                'aweme_id': data['aweme_id'],
                'create_time': data['create_time'],
                'duration': data['duration'],
                'desc': data['desc'],
                'share_url': data['share_url']
            }
        }
        self.desc = data['desc']
        self.aweme_id = data['aweme_id']

    @staticmethod
    def builder(data):
        if data.get('images', None) is None:
            return VideoItem(data)
        else:
            # return ImagesItem(data)
            print("没有实现图集的获取:{}".format(data['aweme_id']))
            # TODO: 实现图集的获取
            return None


class VideoItem(AwemeItem):
    # bit_rate = 0
    # url_list = None  # ->list
    # format = None  # 'mp4'
    # height = 0
    # width = 0
    # datasize = 0
    # file_hash = None
    url_list = None
    format = None

    def __init__(self, data):
        super().__init__(data)
        video = data['video']['bit_rate'][0]  # 根据观察，第一个位置的视频bitrate最大
        video_dict = {
            'bit_rate': video['bit_rate'],
            'format': video['format'],
            'height': video['play_addr']['height'],
            'width': video['play_addr']['width'],
            'datasize': video['play_addr']['data_size'],
            'file_hash': video['play_addr']['file_hash']
        }
        self.data['video'] = video_dict
        self.format = video['format']
        self.url_list = video['play_addr']['url_list']


class ImagesItem(AwemeItem):
    def __init__(self, data):
        super().__init__(data)


# 本类内部实现：
# 1.基于queue的多线程下载
# 2.本地存储
class DownloadHelper:
    path = 'likes'

    download_queue = None

    def __init__(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        self.download_queue = Queue()

    @staticmethod
    def sanitize_path(title):
        # 定义非法字符
        illegal_chars = '<>:"/\\|?*\t\n'
        for char in illegal_chars:
            title = title.replace(char, ' ')
        return title

    # 返回下载大小
    def download_by_url(self, url, title, format, subfolder="", file_size_threshold=1024):
        if subfolder != "":
            subfolder = self.sanitize_path(subfolder)
            if not os.path.exists(subfolder):
                os.makedirs(subfolder)

        response = requests.get(url)  # TODO: 请求资源文件时，在headers中包含cookies
        file_size = len(response.content)

        if file_size > file_size_threshold:
            title = title[0:120]
            title = self.sanitize_path(title) + '.' + format
            filepath = os.path.join(self.path, subfolder, title)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            local_file_status = True
        else:
            local_file_status = False
            # 文件不满足大小要求，可能被反爬虫
        response.close()
        return file_size, local_file_status

    thread_number_lock = threading.Lock()
    alive_thread_number = 0

    # 该方法会阻塞调用进程，直到当前队列中的所有内容被下载完毕
    # 更改：有些视频比较大，为防止长等待，更改阻塞条件为【当开启的50%线程都在运行时】
    def start_download(self, aweme_item_list=[] ,num_workers=4):
        for aweme_item in aweme_item_list:
            self.download_queue.put_nowait(aweme_item)
        threads = [threading.Thread(target=self.__workder__, name='worker{}'.format(i)) for i in range(num_workers)]
        for thread in threads:
            thread.start()
        # print("对于本轮下载，启动了{}个下载进程".format(num_workers))
        # for thread in threads:
        #     thread.join()
        alive_threshold = num_workers / 2
        self.alive_thread_number = num_workers
        while True:
            with self.thread_number_lock:
                if self.alive_thread_number < alive_threshold:
                    break
            time.sleep(2)

    def __workder__(self):
        while not self.download_queue.empty():
            aweme = self.download_queue.get()
            if isinstance(aweme, VideoItem):
                status = False
                for url in aweme.url_list:
                    filesize, status = self.download_by_url(url, "{}_{}".format(aweme.aweme_id, aweme.desc), aweme.format)
                    if status:
                        break
                if status:
                    local_record.add_by_id(aweme.aweme_id, aweme.data)
                    print("successfully downloaded ", aweme.aweme_id)
                else:
                    local_record.add_failed_by_id(aweme.aweme_id, aweme.data)
                    print("fail to download ", aweme.aweme_id)

            elif isinstance(aweme, ImagesItem):
                print("undefined download ImageItem: at worker")  # TODO: download aweme:images
            else:
                print("undefined download: at worker")
        with self.thread_number_lock:
            self.alive_thread_number = self.alive_thread_number - 1


download_helper = DownloadHelper()

class LogParser:
    def __init__(self):
        pass

    prefix_url_like = r"https://www.douyin.com/aweme/v1/web/aweme/favorite/?"

    def get_likes_request_id_list(self, logs):
        logs = [json.loads(_["message"])["message"] for _ in logs]
        ids = [log["params"]["requestId"] for log in logs
               if
               log["method"] == "Network.responseReceived" and log["params"]["response"]["url"].startswith(
                   self.prefix_url_like)
               ]
        return ids

    """
    :response_body json响应文件
    """
    def get_likes_aweme_list(self, response_body) -> (list, bool):
        data = json.loads(response_body)
        has_more = data['has_more'] == 1
        aweme_item_list = []
        aweme_list = data['aweme_list']  # list of dict
        for aweme_data in aweme_list:
            aweme_item = AwemeItem.builder(aweme_data)
            if aweme_item is not None:
                aweme_item_list.append(aweme_item)
        return aweme_item_list, has_more


log_parser = LogParser()
