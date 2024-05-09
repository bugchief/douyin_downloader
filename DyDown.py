import time

from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from dydown_utils import log_parser
from dydown_utils import download_helper
from dydown_utils import local_record

# 获取webdriver对象，开启performance log
options = Options()
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
driver = webdriver.Chrome(options=options)

# 启用网络监控
driver.execute_cdp_cmd('Network.enable', {})

driver.get("https://www.douyin.com")

# 等待扫码登录完成
WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "login-pannel")))

WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.ID, "login-pannel")))

# 清空log
driver.get_log('performance')

# 跳转喜欢页面
driver.get("https://www.douyin.com/user/self?showTab=like")
time.sleep(5)

# 1.从performance log中拉取当前所有的response，
# 2.找到request url前缀匹配的requestID
# 3.根据requestID找到responseBody
# 4.在body中找到作品具体信息，将其加入一个待下载队列queue
# 5.启动多个线程处理queue中的作品，下载到本地。直到queue空时，结束线程
# 6.线程join到主线程，也就是等待当页下载完成再刷新下一页
# 7.直到hasmore=0时停止循环


try:
    local_record.open()
    has_more = True
    while has_more:
        # TODO 对验证码弹出的判定

        # 执行页面滚动
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # 获取性能日志
        logs = driver.get_log('performance')

        # 解析log，获取（喜欢列表） 的http request id
        request_ids = log_parser.get_likes_request_id_list(logs)

        for request_id in request_ids:
            # 获取responseBody
            response = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
            # 解析当前aweme_list和has_more
            aweme_item_list, has_more = log_parser.get_likes_aweme_list(response['body'])
            # 传入下载器，开始多线程并行下载，下载期间主线程阻塞
            download_helper.start_download(aweme_item_list, num_workers=8)

        # 判断最后一个response是否有has more
        # 此处假设request_id是按请求顺序获得的，所以不必做多余逻辑判断
finally:
    local_record.save()
