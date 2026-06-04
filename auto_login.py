# -*- coding: utf-8 -*-
# ==============================================================================
# 导入所需的各种模块
# ==============================================================================
import time            # 用于控制程序暂停、等待
import os              # 用于读取系统环境变量（如账号、代理）和创建文件夹
import base64          # 用于解码图片验证码的 Base64 数据
import sys             # 用于控制程序退出
import re              # 正则表达式，用于从文本中提取数字（如积分余额）
import random          # 用于产生随机数，比如随机挑选浏览器身份
import asyncio         # 异步框架，Zendriver 引擎运行必须依赖它
from urllib.parse import urlparse  # 用于解析网址，提取域名

# --- 主力业务引擎 ---
from seleniumbase import SB
import ddddocr         # 强大的本地离线验证码识别库

# --- 先遣破盾引擎 (底层 CDP 协议) ---
import zendriver
from zendriver.core.element import Element
import latest_user_agents  # 获取互联网上最新真实浏览器的身份列表

# ==============================================================================
# 1. 网站配置与辅助功能区域
# ==============================================================================
CONFIG = {
    "target_url": "https://run.freecloud.ltd/login",              # 登录网址
    "username_selector": "#emailInp",                             # 账号输入框
    "password_selector": "#emailPwdInp",                          # 密码输入框
    "captcha_img_selector": "#allow_login_email_captcha",         # 验证码图片
    "captcha_input_selector": "#captcha_allow_login_email_captcha",# 验证码输入框
    "login_btn_selector": 'button[type="submit"]',                # 登录按钮
    "user_center_selector": 'a[href="clientarea"]',               # 用户中心链接(用于判断是否登录成功)
    
    "sign_in_url": 'https://run.freecloud.ltd/addons?_plugin=5&_controller=index&_action=index', # 签到网址
    "sign_in_btn_selector": 'button[onclick="showMathVerification()"]', # 签到按钮
    "math_question_selector": '#mathQuestion',                    # 算术题文本
    "math_input_selector": '#userAnswer',                         # 算术题答案输入框
    "verify_btn_selector": 'button[onclick="checkAnswer()"]',     # 提交答案按钮
    "popup_content_selector": ".layui-layer-content",             # 弹窗提示内容
    "popup_confirm_btn_selector": ".layui-layer-btn0",            # 弹窗确认按钮
    "points_balance_selector": "div.alert-success span",          # 积分余额文本
    
    "server_list_url": "https://run.freecloud.ltd/service?groupid=305", # 云服务器列表页
    "server_checkbox_selector": '.row-checkbox',                  # 勾选云服务器的复选框
    "list_renew_btn_selector": '#readBtn',                        # 列表页的续费按钮
    "confirm_renew_btn_selector": '.xfSubmit',                    # 确认续费按钮
    "order_pay_btn_selector": '#payamount',                       # 订单支付按钮
    "modal_pay_btn_selector": 'button.pay-now'                    # 弹窗内的立即支付按钮
}

# 自动在当前目录下创建一个名为 screenshots 的文件夹，如果已存在则不报错
os.makedirs("screenshots", exist_ok=True)

def take_screenshot(sb, step_name, username="system"):
    """
    【截图辅助函数】
    作用：将当前浏览器的实时画面保存下来。在没有显示器的 GitHub 虚拟机里，这是我们排错的唯一“眼睛”。
    """
    # 替换账号里的特殊字符，防止作为文件名时报错
    safe_name = username.replace("@", "_").replace(".", "_")
    filepath = f"screenshots/{safe_name}_{step_name}.png"
    try:
        sb.save_screenshot(filepath)
        print(f"    📸 已截图保存: {filepath}")
    except Exception:
        pass

# ==============================================================================
# 2. 【核心引擎】Zendriver 先遣破盾模块
# ==============================================================================
def get_chrome_user_agent():
    """
    作用：从最新列表中随机抽取真实的 Chrome User-Agent（浏览器指纹身份证）。
    防止每次请求都是同一个固定身份，从而被 Cloudflare 识破。
    """
    chrome_user_agents = [
        ua for ua in latest_user_agents.get_latest_user_agents()
        if "Chrome" in ua and "Edg" not in ua
    ]
    return random.choice(chrome_user_agents)

async def fetch_cf_clearance(target_url, proxy_url):
    """
    【阶段一：底层破盾】
    利用 Zendriver 启动浏览器，绕过常规 DOM 限制，直接透过 shadow_root 发出底层电信号，
    抢夺 Cloudflare 的“免死金牌” (名为 cf_clearance 的 Cookie)。
    """
    ua = get_chrome_user_agent()
    
    # 实例化配置对象，加入 no_sandbox=True 允许 root 权限运行
    config = zendriver.Config(headless=False, no_sandbox=True)
    
    # 🛠️ 针对 GitHub Actions 虚拟机的专属环境优化参数
    config.add_argument("--no-sandbox")               # 强行禁用沙盒模式，突破 root 权限限制
    config.add_argument("--disable-dev-shm-usage")    # 突破共享内存限制，防止浏览器因为内存不足崩溃闪退
    config.add_argument("--disable-gpu")              # 虚拟机没有显卡，禁用 GPU 加速
    config.add_argument(f"--user-agent={ua}")         # 穿上随机挑选的合法“身份证”
    
    if proxy_url:
        config.add_argument(f"--proxy-server={proxy_url}") # 挂载我们配置好的代理 IP
    
    # 启动 Zendriver 浏览器实例
    driver = zendriver.Browser(config)
    await driver.start()
    
    print(f"    🛡️ [先遣部队] 启动 Zendriver 底层 CDP 协议，正向目标进发...")
    
    try:
        await driver.get(target_url)
        start_time = time.time()
        final_cookies = []
        
        # 给它 45 秒的时间与 Cloudflare 的 5 秒盾进行对抗
        while time.time() - start_time < 45:
            # 1. 检查浏览器有没有收到 CF 颁发的“免死金牌”
            cookies = await driver.cookies.get_all()
            final_cookies = [c.to_json() for c in cookies]
            if any(c["name"] == "cf_clearance" for c in final_cookies):
                print("    ✅ [先遣部队] 破盾成功！已拿到 cf_clearance Cookie。")
                break
            
            # 2. 如果卡在“请验证您是真人”的框框，利用 CDP 协议直接穿透 shadow_root 强制点击
            try:
                widget_input = await driver.main_tab.find("input")
                # 寻找隐藏着验证码按钮的影子 DOM 节点
                if widget_input and widget_input.parent and widget_input.parent.shadow_roots:
                    challenge = Element(
                        widget_input.parent.shadow_roots[0],
                        driver.main_tab,
                        widget_input.parent.tree,
                    )
                    # 抓取深层嵌套的点击区块并发出物理点击信号
                    if challenge.children:
                        challenge_btn = challenge.children[0]
                        if "display: none;" not in challenge_btn.attrs.get("style", ""):
                            await asyncio.sleep(1)
                            await challenge_btn.mouse_click()
                            print("    🖱️ [先遣部队] 检测到隐藏复选框，已使用底层电信号完成穿透点击。")
            except Exception:
                pass
            
            # 休息一下，防止发包过快被拉黑
            await asyncio.sleep(1.5)
            
        # 无论成功失败，都把当前的浏览器身份和 Cookie 战利品返回出去
        return ua, final_cookies
    except Exception as e:
        print(f"    ❌ [先遣部队] 执行任务遭遇异常: {e}")
        return ua, []
    finally:
        # 关闭先遣部队的浏览器，释放内存
        await driver.stop()

# ==============================================================================
# 3. 单账号自动化处理流水线 (主力部队)
# ==============================================================================
def process_single_account(username, password):
    print(f"\n==========================================")
    print(f"➡️ 开始处理账号: {username}")
    print(f"==========================================")
    
    # 获取我们在 workflow (YML) 中设置好的可用代理
    env_proxy = os.environ.get("HTTP_PROXY")
    
    # === 阶段一：唤醒先遣部队破盾 ===
    try:
        # 运行异步的 fetch_cf_clearance 函数
        ua, cookies_list = asyncio.run(fetch_cf_clearance(CONFIG['target_url'], env_proxy))
    except Exception as e:
        print(f"    ❌ 获取验证 Cookie 遇到系统错误：{e}")
        return

    # 检查战利品：如果没有拿到 cf_clearance，说明 IP 已经太脏了，被 CF 彻底拒之门外
    if not any(c['name'] == 'cf_clearance' for c in cookies_list):
        print("    ❌ 突破失败，未能拿到免死金牌。可能是该代理节点被 CF 彻底封杀，跳过该账号。")
        return
        
    print(f"\n>>> 🤖 [主力部队] 携带战利品 (Cookie) 启动业务主引擎...")
    
    # === 阶段二：主力部队接管业务 ===
    # 启动 SeleniumBase（非常关键：必须伪装得和先遣部队的 User-Agent 身份一模一样，否则 Cookie 验证会失效）
    with SB(
        uc=True,            
        test=True,          
        locale="zh-CN",      
        headless=False,      
        proxy=env_proxy,    
        chromium_arg=f"--disable-blink-features=AutomationControlled,--window-size=1920,1080,--user-agent={ua}"
    ) as sb:
        
        # ⚠️ 高级技巧：为了种入拿到手的 Cookie，必须先访问该域名下一个不存在的页面建立安全上下文
        parsed_url = urlparse(CONFIG['target_url'])
        domain = parsed_url.netloc
        setup_url = f"https://{domain}/404_setup_cookies_page_not_found"
        sb.driver.get(setup_url)
        
        # 将先遣部队拿到的所有 Cookie（包括 cf_clearance）完整注射到当前的业务浏览器中
        for cookie in cookies_list:
            try:
                c_dict = {'name': cookie['name'], 'value': cookie['value'], 'domain': cookie['domain']}
                if 'path' in cookie: c_dict['path'] = cookie['path']
                if 'secure' in cookie: c_dict['secure'] = cookie['secure']
                sb.driver.add_cookie(c_dict)
            except Exception:
                pass
                
        print("    🍪 已成功向业务引擎注入全套安全凭据！开始全自动奔放操作...")
        
        # 此时再访问登录页，CF 防火墙会查验刚刚种入的 Cookie，直接隐形放行！
        sb.open(CONFIG['target_url'])
        time.sleep(4)
        take_screenshot(sb, "01_初始访问页面", username)

        try:
            # ------------------------------------------------------------------
            # 登录模块 (智能识图与提交流程)
            # ------------------------------------------------------------------
            login_success = False 
            for login_attempt in range(2):
                print(f"    ▶ 开始第 {login_attempt + 1} 次尝试登录...")
                captcha_success = False 
                
                # 图片验证码最多尝试识别 10 次
                for captcha_attempt in range(10):
                    sb.wait_for_element(CONFIG['captcha_img_selector'], timeout=10)
                    img_src = sb.get_attribute(CONFIG['captcha_img_selector'], "src")
                    
                    if img_src and "base64," in img_src:
                        # 切割出 Base64 编码的图片数据并进行离线 OCR 识别
                        base64_data = img_src.split(',')[1]
                        img_bytes = base64.b64decode(base64_data)
                        ocr = ddddocr.DdddOcr(show_ad=False)
                        captcha_text = ocr.classification(img_bytes)
                        
                        # 确保验证码是纯数字才提交（增加准确率）
                        if captcha_text.isdigit():
                            print(f"      ✅ 验证码识别成功: {captcha_text}")
                            captcha_success = True
                            break
                        else:
                            print(f"      ⚠️ 识别结果含字母/乱码 ({captcha_text})，点击刷新重试...")
                            sb.click(CONFIG['captcha_img_selector'])
                            time.sleep(2)
                    else:
                        break
                
                if not captcha_success:
                    print("    🚨 致命错误：验证码连续识别失败。放弃当前账号。")
                    return

                # 表单自动填充
                sb.clear(CONFIG['username_selector'])
                sb.type(CONFIG['username_selector'], username)
                
                sb.clear(CONFIG['password_selector'])
                sb.type(CONFIG['password_selector'], password)
                
                sb.clear(CONFIG['captcha_input_selector'])
                sb.type(CONFIG['captcha_input_selector'], captcha_text)
                
                # 提交表单
                sb.click(CONFIG['login_btn_selector'])
                time.sleep(5)
                
                # 校验是否成功进入后台仪表盘
                if sb.is_element_present(CONFIG['user_center_selector']):
                    login_success = True
                    print(f"    📄 登录成功！")
                    break 
                else:
                    print(f"    ⚠️ 登录可能失败，准备刷新重试...")
                    sb.refresh() 
                    time.sleep(3)
            
            if not login_success:
                print("    ❌ 彻底登录失败，放弃当前账号。")
                return 

            # ------------------------------------------------------------------
            # 签到赚积分模块 (全自动读取算术题并作答)
            # ------------------------------------------------------------------
            print("\n>>> 🎁 准备执行每日签到任务...")
            sb.open(CONFIG['sign_in_url'])
            time.sleep(4) 
            
            balance_value = 0.0 
            # 允许系统刷出遇到除不尽的题目时刷新，最多刷新5次
            for attempt in range(5):
                sb.click(CONFIG['sign_in_btn_selector'])
                time.sleep(2) 
                
                # 获取网页上如 "请计算：3+5=" 的文本内容
                question_text = sb.get_text(CONFIG['math_question_selector'])
                # 把中文清洗掉，只保留数学表达式 "3+5"
                math_expr = question_text.replace("请计算：", "").replace("=", "").strip()
                # 让 Python 的内置函数计算结果
                result = eval(math_expr)
                
                # 遇到除不尽的小数，刷新页面换题
                if isinstance(result, float) and not result.is_integer():
                    sb.refresh() 
                    time.sleep(3)
                    continue     
                
                final_answer = int(result) 
                print(f"    ✅ 算术计算完毕: {final_answer}，正在提交...")
                
                # 填入答案并提交
                sb.clear(CONFIG['math_input_selector']) 
                sb.type(CONFIG['math_input_selector'], str(final_answer))
                sb.click(CONFIG['verify_btn_selector'])
                
                # 抓取签到系统弹出的反馈（成功/已签到）
                sb.wait_for_element(CONFIG['popup_content_selector'], timeout=5)
                print(f"    🔔 签到提示: 【{sb.get_text(CONFIG['popup_content_selector'])}】")
                
                # 关掉弹窗，刷新页面同步一下积分数据
                sb.click(CONFIG['popup_confirm_btn_selector'])
                time.sleep(2) 
                sb.refresh()
                time.sleep(4)
                
                try:
                    # 使用正则提取积分数值（例如提取"可用积分: 5.26"中的 5.26）
                    balance_text = sb.get_text(CONFIG['points_balance_selector'])
                    match = re.search(r"(\d+(?:\.\d+)?)", balance_text)
                    if match:
                        balance_value = float(match.group(1))
                        print(f"    💰 当前可用积分: {balance_value}")
                except Exception:
                    pass
                break 

            # ------------------------------------------------------------------
            # 云服务器自动续费模块
            # ------------------------------------------------------------------
            # 判断剩余积分是否足够（假设云服务器续费价格 > 0.25 才能发起）
            if balance_value > 0.25:
                print(f">>> 💻 积分达标，执行自动续费...")
                sb.open(CONFIG['server_list_url'])
                time.sleep(4) 
                take_screenshot(sb, "8_云服务器列表页", username)
                
                # 检测页面有没有待续费的产品
                if sb.is_element_present(CONFIG['server_checkbox_selector']):
                    sb.click(CONFIG['server_checkbox_selector'])
                    sb.js_click(CONFIG['list_renew_btn_selector'])
                    time.sleep(4) 
                    
                    # 生成订单流水并确认
                    sb.wait_for_element_visible(CONFIG['confirm_renew_btn_selector'], timeout=10)
                    sb.scroll_to(CONFIG['confirm_renew_btn_selector'])
                    sb.click(CONFIG['confirm_renew_btn_selector'])   
                    time.sleep(5) 
                    
                    # 在支付弹窗点击确认支付
                    sb.wait_for_element(CONFIG['order_pay_btn_selector'], timeout=15)
                    sb.js_click(CONFIG['order_pay_btn_selector']) 
                    
                    sb.wait_for_element(CONFIG['modal_pay_btn_selector'], timeout=10)
                    sb.js_click(CONFIG['modal_pay_btn_selector']) 
                    print("    ▶ 💸 支付确认完成，等待系统处理...")
                    
                    time.sleep(8) 
                    take_screenshot(sb, "12_支付完成跳转", username)
                    
                    # 读取网页上更新后的到期时间打印出来
                    try:
                        p_elements = sb.find_elements('section.text-gray p')
                        for p in p_elements:
                            if "到期时间" in p.text:
                                print(f"    📅 续费成功！最新 {p.text}")
                                break
                    except Exception:
                        pass
                else:
                    print("    ⚠️ 当前账号未检测到可续费产品。")
            else:
                print(f">>> 🛑 积分不足 (当前 {balance_value})，安全结束。")

        except Exception as e:
            # 捕获未知错误，保证脚本不会因为单个账号崩溃而全盘挂掉
            print(f"    ❌ 业务执行崩溃: {e}")
            take_screenshot(sb, "Error_业务报错", username)

# ==============================================================================
# 4. 主程序入口区
# ==============================================================================
def main():
    print("🚀 自动化任务启动 (双引擎破盾架构)...")
    
    # 从系统环境变量读取我们配置好的账号密码（格式：账号1:密码1,账号2:密码2）
    accounts_str = os.environ.get("acount")
    if not accounts_str:
        print("⚠️ 未获取到名为 'acount' 的环境变量，请在 GitHub Secrets 里配置！")
        return

    # 按逗号拆分出每一组账号
    account_list = accounts_str.split(',')
    print(f"📋 共检测到 {len(account_list)} 个待处理账号。")
    
    # 用循环逐个处理
    for item in account_list:
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1) 
            # 将账号和密码传入处理流水线
            process_single_account(parts[0].strip(), parts[1].strip())
            
    print("\n🏁 所有列队任务执行完毕！")

# 约定俗成的 Python 执行起点
if __name__ == "__main__":
    main()
