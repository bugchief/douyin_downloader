# douyin_downloader
批量采集抖音喜欢视频（基于Selenium）

# 声明
- 学习用途，仅供交流

# 使用说明
1. selenium + chrome webdriver
2. run `DyDown.py`
3. 在弹出的Chrome中扫码登录，页面将自动跳转至**喜欢**页面滚动采集视频
4. 采集的视频保存在文件夹`likes`中，本次采集中所有的视频信息保存在`normal.json`，采集失败的视频信息保存在`failed.json`中。
