# -*- coding: utf-8 -*-
import time
import os
import base64
import sys
import re  
import random
from seleniumbase import SB
import ddddocr

# ==========================================
# 1. 网站配置区域 (定义所有需要用到的网页元素定位器)
# ==========================================
CONFIG = {
    "target_url": "https://run.freecloud.ltd/login",
    "username_selector": "#emailInp",             
    "password_selector": "#emailPwdInp",          
    "captcha_img_selector": "#allow_login_email_captcha",          
    "captcha_input_selector": "#captcha_allow_login_email_captcha", 
    "login_btn_selector": 'button[type="submit"]',
    
    "user_center_selector": 'a[href="clientarea"]',
    
    "sign_in_url": 'https://run.freecloud.ltd/addons?_plugin=5&_controller=index&_action=index',
    "sign_in_btn_selector": 'button[onclick="showMathVerification()"]', 
    "math_question_selector": '#mathQuestion',                       
    "math_input_selector": '#userAnswer',                            
    "verify_btn_selector": 'button[onclick="checkAnswer()"]',        
    "popup_content_selector": ".layui-layer-content", 
    "popup_confirm_btn_selector": ".layui-layer-btn0", 
    "points_balance_selector": "div.alert-success span",
    
    "server_list_url": "https://run.freecloud.ltd/service?groupid=305", 
    "server_checkbox_selector": '.row-checkbox',              
    "list_renew_btn_selector": '#readBtn',                    
    "confirm_renew_btn_selector": '.xfSubmit',          
    "order_pay_btn_selector": '#payamount',                    
    "modal_pay_btn_selector": 'button.pay-now'                
}

# 自动创建一个文件夹用来保存运行时的截图
os.makedirs("screenshots", exist_ok=True)

def take_screenshot(sb, step_name, username="system"):
    """
    截图辅助函数：将当前浏览器画面保存下来，方便我们在 GitHub 日志里排查错误。
    """
    safe_name = username.replace("@", "_").replace(".", "_")
    filepath = f"screenshots/{safe_name}_{step_name}.png"
    try:
        sb.save_screenshot(filepath)
        print(f"    📸 已截图保存: {filepath}")
    except Exception as e:
        print(f"    ⚠️ 截图失败 ({filepath}): {e}")

# ==========================================
# 2. Cloudflare 绕过辅助函数 (核心修复区)
# ==========================================
def is_cloudflare_interstitial(sb) -> bool:
    """
    判断当前页面是否被 Cloudflare 的“5秒盾”拦截。
    已新增中文特征词，防止漏判。
    """
    try:
        page_source = sb.get_page_source()
        title = sb.get_title().lower() if sb.get_title() else ""
        
        # 包含了英文和中文的拦截页面特征
        indicators = [
            "Just a moment", "Verify you are human", "Checking your browser", 
            "Checking if the site connection is secure",
            "正在进行安全验证", "请验证您是真人", "challenges.cloudflare.com"
        ]
        
        # 只要网页源码里包含了上面的任意一句话，就说明被拦截了
        for ind in indicators:
            if ind in page_source:
                return True
                
        if "just a moment" in title or "attention required" in title:
            return True
            
        body_len = sb.execute_script('(function() { return document.body ? document.body.innerText.length : 0; })();')
        if body_len is not None and body_len < 200 and "challenges.cloudflare.com" in page_source:
            return True
            
        return False
    except:
        return False

def bypass_cloudflare_interstitial(sb, max_attempts=4) -> bool:
    """
    尝试绕过最初的 Cloudflare 5秒盾检测。
    """
    print("    🛡️ 检测到 CF 5秒盾，准备破除...")
    for attempt in range(max_attempts):
        print(f"      ▶ 尝试绕过 ({attempt+1}/{max_attempts})...")
        try:
            sb.uc_gui_click_captcha()
            time.sleep(6)
            if not is_cloudflare_interstitial(sb):
                print("      ✅ CF 5秒盾已通过！")
                return True
        except Exception as e:
            pass
        time.sleep(3)
    return False

def handle_turnstile_verification(sb) -> bool:
    """
    处理 Cloudflare 真人复选框验证（Turnstile），并智能等待页面跳转。
    """
    try:
        cookie_btn = 'button[data-cky-tag="accept-button"]'
        if sb.is_element_visible(cookie_btn):
            sb.click(cookie_btn)
            time.sleep(1)
    except:
        pass

    # 把验证码滚动到屏幕中间
    sb.execute_script('''
        try {
            var t = document.querySelector('.cf-turnstile') || 
                    document.querySelector('iframe[src*="challenges.cloudflare"]') || 
                    document.querySelector('iframe[src*="turnstile"]');
            if (t) t.scrollIntoView({behavior:'smooth', block:'center'});
        } catch(e) {}
    ''')
    time.sleep(2)

    has_turnstile = False
    for _ in range(15):
        if (sb.is_element_present('iframe[src*="challenges.cloudflare"]') or 
            sb.is_element_present('iframe[src*="turnstile"]') or 
            sb.is_element_present('.cf-turnstile') or 
            sb.is_element_present('input[name="cf-turnstile-response"]')):
            has_turnstile = True
            break
        time.sleep(1)

    if not has_turnstile:
        print("    🟢 无感验证通过 (未发现 Turnstile)")
        return True

    print("    🧩 发现验证码，执行拟人点击...")
    try:
        # 让浏览器模拟鼠标去点击验证码框
        sb.uc_gui_click_captcha()
    except Exception as e:
        print(f"      ⚠️ 点击动作可能未生效，交由后续智能等待处理: {e}")
        
    print("    ⏳ 正在等待 Cloudflare 验证完成并重定向至目标网站...")
    
    # 【核心修复】：耐心等待真正的目标输入框（#emailInp）出现，最长等 25 秒
    # 这样就不会在页面还没跳转时，就傻傻地去寻找图片验证码从而导致程序崩溃了
    try:
        sb.wait_for_element_visible('#emailInp', timeout=25)
        print("    ✅ 验证通过，已成功进入最终登录页面！")
        return True
    except Exception:
        print("    ❌ 验证超时：Cloudflare 拦截未能通过，卡在了验证页面。")
        return False

# ==========================================
# 3. 单个账号的处理流程 (核心业务逻辑)
# ==========================================
def process_single_account(username, password):
    print(f"\n==========================================")
    print(f"➡️ 开始处理账号: {username}")
    print(f"==========================================")
    
    env_proxy = os.environ.get("HTTP_PROXY")
    
    # 随机选一个真实的 Windows 浏览器身份（UA），让每个账号看起来像不同的人在使用
    windows_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edge/122.0.0.0"
    ]
    random_ua = random.choice(windows_user_agents)
    
    # 启动高匿名的 SeleniumBase 浏览器
    with SB(
        uc=True,            
        test=True,          
        locale="zh-CN",      # 设定为中文，配合国内代理
        headless=False,      
        proxy=env_proxy,    
        chromium_arg=f"--disable-blink-features=AutomationControlled,--window-size=1920,1080,--user-agent={random_ua}"
    ) as sb:
        
        # ---------------------------------------------------------------------
        # 高阶防封注入：修改底层指纹，隐藏 Linux 痕迹，伪装成正常 Windows 电脑
        # ---------------------------------------------------------------------
        fingerprint_spoof_js = """
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); 
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });        

        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
            const imageData = originalGetImageData.apply(this, arguments);
            const len = imageData.data.length;
            if (len >= 4) {
                // 每次请求 Canvas 画布都在右下角加入极小干扰，让机器指纹变成全新且唯一
                imageData.data[len - 4] = imageData.data[len - 4] + (Math.random() > 0.5 ? 1 : -1);
                imageData.data[len - 3] = imageData.data[len - 3] + (Math.random() > 0.5 ? 1 : -1); 
                imageData.data[len - 2] = imageData.data[len - 2] + (Math.random() > 0.5 ? 1 : -1); 
            }
            return imageData;
        };

        const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(p) {
            if (p === 37445) return 'Google Inc. (NVIDIA)'; 
            if (p === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)'; 
            return originalGetParameter.apply(this, arguments);
        };
        """
        sb.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": fingerprint_spoof_js})
        print("    🛡️ [高级防护] 底层 Canvas 动态混淆和独立显卡指纹伪装已顺利挂载！")
        
        print(f"🌐 正在访问目标网站: {CONFIG['target_url']}")
        sb.uc_open_with_reconnect(CONFIG['target_url'], reconnect_time=8)
        time.sleep(4)
        
        take_screenshot(sb, "01_初始访问页面", username)

        page_source = sb.get_page_source()
        if "Error 1005" in page_source or "Access denied" in page_source:
            print("🚨 致命错误：当前代理节点的 IP 被彻底封锁 (Error 1005)！")
            take_screenshot(sb, "Error_1005_节点被封锁", username)
            sys.exit(1)

        # ---------------------------------------------------------------------
        # 拦截与重试逻辑
        # ---------------------------------------------------------------------
        cf_blocked = is_cloudflare_interstitial(sb)
        if cf_blocked:
            if bypass_cloudflare_interstitial(sb):
                print("    ✅ CF 首次绕过成功。")
            else:
                print("    ❌ 首次绕过 CF 失败，等待 5 秒后重试登录流程...")
                time.sleep(5)
                sb.uc_open_with_reconnect(CONFIG['target_url'], reconnect_time=8)
                time.sleep(4)

                if is_cloudflare_interstitial(sb):
                    if not bypass_cloudflare_interstitial(sb):
                        print("    ❌ 重试后仍然无法绕过 Cloudflare，跳过当前账号。")
                        take_screenshot(sb, "CF_绕过失败跳过账号", username)
                        return  
                    else:
                        print("    ✅ 重试后 CF 已放行。")
                else:
                    print("    ✅ 重试后未检测到 CF 阻挡，可以继续。")
        else:
            print("    🟢 未检测到 CF 5秒盾。")

        # ---------------------------------------------------------------------
        # 真人验证与容错保护
        # ---------------------------------------------------------------------
        # 如果卡死在 CF 页面进不去真正的登录页，直接退出当前账号（return），防止后续报错
        if not handle_turnstile_verification(sb):
            print("    ❌ 无法绕过 Cloudflare 验证，跳过当前账号的后续任务。")
            take_screenshot(sb, "CF_彻底拦截失败", username)
            return  
            
        time.sleep(2)
        take_screenshot(sb, "2_准备填写表单", username)

        try:
            # ---------------------------------------------------------------------
            # 登录模块 (包含图片验证码识别)
            # ---------------------------------------------------------------------
            login_success = False 
            for login_attempt in range(2):
                print(f"    ▶ 开始第 {login_attempt + 1} 次尝试登录...")
                captcha_success = False 
                
                # 最多尝试 10 次识别验证码
                for captcha_attempt in range(10):
                    sb.wait_for_element(CONFIG['captcha_img_selector'], timeout=10)
                    img_src = sb.get_attribute(CONFIG['captcha_img_selector'], "src")
                    
                    if img_src and "base64," in img_src:
                        base64_data = img_src.split(',')[1]
                        img_bytes = base64.b64decode(base64_data)
                        ocr = ddddocr.DdddOcr(show_ad=False)
                        captcha_text = ocr.classification(img_bytes)
                        
                        # 确保验证码是纯数字才提交
                        if captcha_text.isdigit():
                            print(f"      ✅ 验证码识别成功 (纯数字): {captcha_text}")
                            captcha_success = True
                            break
                        else:
                            print(f"      ⚠️ 第 {captcha_attempt + 1} 次识别结果含字母/乱码 ({captcha_text})，点击刷新...")
                            sb.click(CONFIG['captcha_img_selector'])
                            time.sleep(2)
                    else:
                        print("      ⚠️ 无法获取验证码图片。")
                        break
                
                if not captcha_success:
                    print("    🚨 致命错误：验证码连续 10 次识别失败！程序将直接退出。")
                    sys.exit(1)

                # 填写账号、密码、验证码并点击登录
                sb.clear(CONFIG['username_selector'])
                sb.type(CONFIG['username_selector'], username)
                
                sb.clear(CONFIG['password_selector'])
                sb.type(CONFIG['password_selector'], password)
                
                sb.clear(CONFIG['captcha_input_selector'])
                sb.type(CONFIG['captcha_input_selector'], captcha_text)
                
                sb.click(CONFIG['login_btn_selector'])
                time.sleep(5)
                
                # 检查是否成功进入用户中心
                if sb.is_element_present(CONFIG['user_center_selector']):
                    login_success = True
                    print(f"    📄 登录验证成功！当前页面: {sb.get_title()}")
                    break 
                else:
                    print(f"    ⚠️ 第 {login_attempt + 1} 次登录似乎失败了（没找到用户中心），正在准备重试...")
                    sb.refresh() 
                    time.sleep(3)
            
            if not login_success:
                print("    ❌ 两次登录尝试均未成功，跳过当前账号的后续任务。")
                return 

            # ---------------------------------------------------------------------
            # 每日签到与积分提取模块
            # ---------------------------------------------------------------------
            print("\n>>> 🎁 准备执行每日签到任务...")
            sb.open(CONFIG['sign_in_url'])
            time.sleep(4) 
            
            balance_value = 0.0 
            max_retries = 5
            for attempt in range(max_retries):
                sb.click(CONFIG['sign_in_btn_selector'])
                time.sleep(2) 
                
                # 抓取签到算术题并计算结果
                question_text = sb.get_text(CONFIG['math_question_selector'])
                math_expr = question_text.replace("请计算：", "").replace("=", "").strip()
                result = eval(math_expr)
                
                # 如果遇到除不尽的算术题，就刷新页面换一道题
                if isinstance(result, float) and not result.is_integer():
                    sb.refresh() 
                    time.sleep(3)
                    continue     
                
                final_answer = int(result) 
                print(f"    ✅ 计算结果为整数: {final_answer}，正在提交...")
                
                sb.clear(CONFIG['math_input_selector']) 
                sb.type(CONFIG['math_input_selector'], str(final_answer))
                sb.click(CONFIG['verify_btn_selector'])
                
                # 读取签到系统弹出的提示信息（比如“签到成功”或“今天已签到”）
                sb.wait_for_element(CONFIG['popup_content_selector'], timeout=5)
                popup_msg = sb.get_text(CONFIG['popup_content_selector'])
                print(f"    🔔 签到系统提示: 【{popup_msg}】")
                
                sb.click(CONFIG['popup_confirm_btn_selector'])
                time.sleep(2) 
                
                print("    🔄 正在强制刷新页面以同步最新的余额数据...")
                sb.refresh()
                time.sleep(4)
                
                # 提取当前的积分余额
                try:
                    balance_text = sb.get_text(CONFIG['points_balance_selector'])
                    print(f"    💰 当前账户原始信息: {balance_text}")
                    match = re.search(r"(\d+(?:\.\d+)?)", balance_text)
                    if match:
                        balance_value = float(match.group(1))
                        print(f"    🔍 提取并转换可用积分为: {balance_value}")
                except Exception:
                    print("    ⚠️ 无法获取积分余额。")

                print("    🎉 签到流程结束。\n")
                break 
            else:
                print("    ❌ 签到失败：连续 5 次刷新都没有遇到可以整除的算术题。")

            # ---------------------------------------------------------------------
            # 积分判断与云服务器续费模块
            # ---------------------------------------------------------------------
            if balance_value > 0.25:
                print(f">>> 💻 积分达标 (当前 {balance_value})，开始执行云服务器续费任务...")
                print("    ▶ 正在强制跳转至云服务器列表网址...")
                sb.open(CONFIG['server_list_url'])
                time.sleep(4) 
                take_screenshot(sb, "8_云服务器列表页", username)
                
                # 查找页面上的复选框来勾选服务器
                if sb.is_element_present(CONFIG['server_checkbox_selector']):
                    sb.click(CONFIG['server_checkbox_selector'])
                    print("    ▶ 已勾选目标云服务器。")
                    
                    sb.js_click(CONFIG['list_renew_btn_selector'])
                    time.sleep(4) 
                    
                    print("    ▶ 正在生成续费订单...")
                    sb.wait_for_element_visible(CONFIG['confirm_renew_btn_selector'], timeout=10)
                    sb.scroll_to(CONFIG['confirm_renew_btn_selector'])
                    sb.click(CONFIG['confirm_renew_btn_selector'])   
                    time.sleep(5) 
                    
                    print("    ▶ 已调起支付面板，等待确认...")
                    sb.wait_for_element(CONFIG['order_pay_btn_selector'], timeout=15)
                    sb.js_click(CONFIG['order_pay_btn_selector']) 
                    
                    sb.wait_for_element(CONFIG['modal_pay_btn_selector'], timeout=10)
                    sb.js_click(CONFIG['modal_pay_btn_selector']) 
                    print("    ▶ 💸 已在弹窗中确认支付，正在等待系统处理并跳转...")
                    
                    time.sleep(8) 
                    take_screenshot(sb, "12_支付完成跳转详情页", username)
                    
                    # 读取续费后的到期时间
                    try:
                        p_elements = sb.find_elements('section.text-gray p')
                        for p in p_elements:
                            if "到期时间" in p.text:
                                print(f"    📅 续费成功！最新 {p.text}")
                                break
                    except Exception as e:
                        pass
                    
                    print("\n>>> 🔄 续费完成，返回签到中心查看最新积分...")
                    sb.open(CONFIG['sign_in_url'])
                    time.sleep(4)
                    take_screenshot(sb, "13_续费后返回签到中心", username)
                    
                    try:
                        final_balance_text = sb.get_text(CONFIG['points_balance_selector'])
                        print(f"    💰 续费后账户最新信息: {final_balance_text}")
                        match = re.search(r"(\d+(?:\.\d+)?)", final_balance_text)
                        if match:
                            print(f"    ✨ 最终剩余可用积分: {float(match.group(1))}")
                    except Exception:
                        print("    ⚠️ 无法获取最终积分余额。")
                else:
                    print("    ⚠️ 当前账号下未检测到可续费的云服务器，已跳过。")
            else:
                print(f">>> 🛑 积分不足 (当前 {balance_value} <= 0.25)，安全退出当前账号的后续操作！")

        except Exception as e:
            # 捕获未知错误，拍下最后一张死亡快照
            print(f"    ❌ 账号处理或执行过程中出现错误: {e}")
            take_screenshot(sb, "Error_程序崩溃截图", username)

# ==========================================
# 4. 主程序入口 (读取 GitHub 环境变量并循环账号)
# ==========================================
def main():
    print("🚀 自动化任务启动...")
    # 从 GitHub 的 Secrets 环境变量读取你的所有账号
    accounts_str = os.environ.get("acount")
    if not accounts_str:
        print("⚠️ 未获取到名为 'acount' 环境变量！")
        return

    # 按逗号切割出多个账号
    account_list = accounts_str.split(',')
    print(f"📋 共检测到 {len(account_list)} 个账号。")
    
    # 逐个执行任务
    for item in account_list:
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1) 
            username = parts[0].strip()
            password = parts[1].strip()
            process_single_account(username, password)
            
    print("\n🏁 所有队列任务已全部执行完成！")

if __name__ == "__main__":
    main()
