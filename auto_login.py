# -*- coding: utf-8 -*-
# ==============================================================================
# 导入所需的各种模块
# ==============================================================================
import time
import os
import base64
import sys
import re  
import random
import asyncio
from urllib.parse import urlparse

# --- 主力业务引擎 ---
from seleniumbase import SB
import ddddocr

# --- 先遣破盾引擎 (底层 CDP 协议) ---
import zendriver
from zendriver.core.element import Element
from zendriver import cdp
from zendriver.cdp.emulation import UserAgentBrandVersion, UserAgentMetadata
import latest_user_agents
import user_agents  

# ==============================================================================
# 1. 网站配置与辅助功能区域
# ==============================================================================
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

os.makedirs("screenshots", exist_ok=True)

def take_screenshot(sb, step_name, username="system"):
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
    chrome_user_agents = [
        ua for ua in latest_user_agents.get_latest_user_agents()
        if "Chrome" in ua and "Edg" not in ua
    ]
    return random.choice(chrome_user_agents)

async def fetch_cf_clearance(target_url, proxy_url):
    ua = get_chrome_user_agent()
    
    config = zendriver.Config(
        headless=False, 
        sandbox=False,                  
        browser_connection_timeout=5,   
        browser_connection_max_tries=20 
    )
    
    config.add_argument("--disable-dev-shm-usage")
    config.add_argument("--disable-gpu")
    
    if proxy_url:
        parsed_proxy = urlparse(proxy_url)
        safe_proxy = f"{parsed_proxy.scheme}://{parsed_proxy.hostname}"
        if parsed_proxy.port:
            safe_proxy += f":{parsed_proxy.port}"
        config.add_argument(f"--proxy-server={safe_proxy}")
    
    driver = zendriver.Browser(config)
    await driver.start()
    print(f"    🛡️ [先遣部队] 启动 Zendriver，正向目标进发...")
    
    try:
        parsed_ua = user_agents.parse(ua)
        metadata = UserAgentMetadata(
            architecture="x86",
            bitness="64",
            brands=[
                UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
                UserAgentBrandVersion(brand="Chromium", version=str(parsed_ua.browser.version[0])),
                UserAgentBrandVersion(brand="Google Chrome", version=str(parsed_ua.browser.version[0])),
            ],
            full_version_list=[
                UserAgentBrandVersion(brand="Not)A;Brand", version="8"),
                UserAgentBrandVersion(brand="Chromium", version=str(parsed_ua.browser.version[0])),
                UserAgentBrandVersion(brand="Google Chrome", version=str(parsed_ua.browser.version[0])),
            ],
            mobile=parsed_ua.is_mobile,
            model=parsed_ua.device.model or "",
            platform=parsed_ua.os.family,      
            platform_version=parsed_ua.os.version_string,
            full_version=parsed_ua.browser.version_string,
            wow64=False,
        )
        
        driver.main_tab.feed_cdp(
            cdp.network.set_user_agent_override(ua, user_agent_metadata=metadata)
        )
        
        await driver.get(target_url)
        start_time = time.time()
        final_cookies = []
        
        while time.time() - start_time < 45:
            cookies = await driver.cookies.get_all()
            final_cookies = [c.to_json() for c in cookies]
            if any(c["name"] == "cf_clearance" for c in final_cookies):
                print("    ✅ [先遣部队] 破盾成功！已拿到 cf_clearance Cookie。")
                return ua, final_cookies
            
            try:
                widget_input = await driver.main_tab.find("input")
                if widget_input and widget_input.parent and widget_input.parent.shadow_roots:
                    challenge = Element(
                        widget_input.parent.shadow_roots[0],
                        driver.main_tab,
                        widget_input.parent.tree,
                    )
                    if challenge.children:
                        challenge_btn = challenge.children[0]
                        if "display: none;" not in challenge_btn.attrs.get("style", ""):
                            await asyncio.sleep(1)
                            try:
                                await challenge_btn.get_position()
                                await challenge_btn.mouse_click()
                                print("    🖱️ [先遣部队] 检测到隐藏复选框，已使用底层电信号完成穿透点击。")
                            except Exception:
                                pass
            except Exception:
                pass
            
            await asyncio.sleep(1.5)
            
        print("    ⚠️ [先遣部队] 45秒超时，未能拿到 Cookie，正在截取失败画面...")
        try:
            await driver.main_tab.save_screenshot("screenshots/zendriver_timeout_fail.png")
        except Exception:
            pass
        return ua, []
        
    except Exception as e:
        print(f"    ❌ [先遣部队] 执行任务遭遇异常: {e}")
        try:
            await driver.main_tab.save_screenshot("screenshots/zendriver_crash.png")
        except:
            pass
        return ua, []
    finally:
        await driver.stop()

# ==============================================================================
# 3. 单账号自动化处理流水线 (主力部队)
# ==============================================================================
def process_single_account(username, password):
    print(f"\n==========================================")
    print(f"➡️ 开始处理账号: {username}")
    print(f"==========================================")
    
    # 🌟 【核心修复点】读取我们刚刚在 YAML 中自定义的安全代理变量名称
    env_proxy = os.environ.get("MY_PROXY")
    
    try:
        ua, cookies_list = asyncio.run(fetch_cf_clearance(CONFIG['target_url'], env_proxy))
    except Exception as e:
        print(f"    ❌ 获取验证 Cookie 遇到系统错误：{e}")
        return

    if not any(c['name'] == 'cf_clearance' for c in cookies_list):
        print("    ❌ 突破失败，未能拿到免死金牌。可能是该代理节点被 CF 彻底封杀，跳过该账号。")
        print("    💡 提示：如果持续失败，请前往 GitHub Actions 运行记录的 Artifacts 下载 screenshots 查看 zendriver 失败截图。")
        return
        
    print(f"\n>>> 🤖 [主力部队] 携带战利品 (Cookie) 启动业务主引擎...")
    
    with SB(
        uc=True,            
        test=True,          
        locale="zh-CN",      
        headless=False,      
        proxy=env_proxy,    
        chromium_arg=f"--disable-blink-features=AutomationControlled,--window-size=1920,1080,--user-agent={ua}"
    ) as sb:
        
        parsed_url = urlparse(CONFIG['target_url'])
        domain = parsed_url.netloc
        setup_url = f"https://{domain}/404_setup_cookies_page_not_found"
        sb.driver.get(setup_url)
        
        for cookie in cookies_list:
            try:
                c_dict = {'name': cookie['name'], 'value': cookie['value'], 'domain': cookie['domain']}
                if 'path' in cookie: c_dict['path'] = cookie['path']
                if 'secure' in cookie: c_dict['secure'] = cookie['secure']
                sb.driver.add_cookie(c_dict)
            except Exception:
                pass
                
        print("    🍪 已成功向业务引擎注入全套安全凭据！开始全自动奔放操作...")
        
        sb.open(CONFIG['target_url'])
        time.sleep(4)
        take_screenshot(sb, "01_初始访问页面", username)

        try:
            login_success = False 
            for login_attempt in range(2):
                print(f"    ▶ 开始第 {login_attempt + 1} 次尝试登录...")
                captcha_success = False 
                
                for captcha_attempt in range(10):
                    sb.wait_for_element(CONFIG['captcha_img_selector'], timeout=10)
                    img_src = sb.get_attribute(CONFIG['captcha_img_selector'], "src")
                    
                    if img_src and "base64," in img_src:
                        base64_data = img_src.split(',')[1]
                        img_bytes = base64.b64decode(base64_data)
                        ocr = ddddocr.DdddOcr(show_ad=False)
                        captcha_text = ocr.classification(img_bytes)
                        
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

                sb.clear(CONFIG['username_selector'])
                sb.type(CONFIG['username_selector'], username)
                
                sb.clear(CONFIG['password_selector'])
                sb.type(CONFIG['password_selector'], password)
                
                sb.clear(CONFIG['captcha_input_selector'])
                sb.type(CONFIG['captcha_input_selector'], captcha_text)
                
                sb.click(CONFIG['login_btn_selector'])
                time.sleep(5)
                
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

            print("\n>>> 🎁 准备执行每日签到任务...")
            sb.open(CONFIG['sign_in_url'])
            time.sleep(4) 
            
            balance_value = 0.0 
            for attempt in range(5):
                sb.click(CONFIG['sign_in_btn_selector'])
                time.sleep(2) 
                
                question_text = sb.get_text(CONFIG['math_question_selector'])
                math_expr = question_text.replace("请计算：", "").replace("=", "").strip()
                result = eval(math_expr)
                
                if isinstance(result, float) and not result.is_integer():
                    sb.refresh() 
                    time.sleep(3)
                    continue     
                
                final_answer = int(result) 
                print(f"    ✅ 算术计算完毕: {final_answer}，正在提交...")
                
                sb.clear(CONFIG['math_input_selector']) 
                sb.type(CONFIG['math_input_selector'], str(final_answer))
                sb.click(CONFIG['verify_btn_selector'])
                
                sb.wait_for_element(CONFIG['popup_content_selector'], timeout=5)
                print(f"    🔔 签到提示: 【{sb.get_text(CONFIG['popup_content_selector'])}】")
                
                sb.click(CONFIG['popup_confirm_btn_selector'])
                time.sleep(2) 
                sb.refresh()
                time.sleep(4)
                
                try:
                    balance_text = sb.get_text(CONFIG['points_balance_selector'])
                    match = re.search(r"(\d+(?:\.\d+)?)", balance_text)
                    if match:
                        balance_value = float(match.group(1))
                        print(f"    💰 当前可用积分: {balance_value}")
                except Exception:
                    pass
                break 

            if balance_value > 0.25:
                print(f">>> 💻 积分达标，执行自动续费...")
                sb.open(CONFIG['server_list_url'])
                time.sleep(4) 
                take_screenshot(sb, "8_云服务器列表页", username)
                
                if sb.is_element_present(CONFIG['server_checkbox_selector']):
                    sb.click(CONFIG['server_checkbox_selector'])
                    sb.js_click(CONFIG['list_renew_btn_selector'])
                    time.sleep(4) 
                    
                    sb.wait_for_element_visible(CONFIG['confirm_renew_btn_selector'], timeout=10)
                    sb.scroll_to(CONFIG['confirm_renew_btn_selector'])
                    sb.click(CONFIG['confirm_renew_btn_selector'])   
                    time.sleep(5) 
                    
                    sb.wait_for_element(CONFIG['order_pay_btn_selector'], timeout=15)
                    sb.js_click(CONFIG['order_pay_btn_selector']) 
                    
                    sb.wait_for_element(CONFIG['modal_pay_btn_selector'], timeout=10)
                    sb.js_click(CONFIG['modal_pay_btn_selector']) 
                    print("    ▶ 💸 支付确认完成，等待系统处理...")
                    
                    time.sleep(8) 
                    take_screenshot(sb, "12_支付完成跳转", username)
                    
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
            print(f"    ❌ 业务执行崩溃: {e}")
            take_screenshot(sb, "Error_业务报错", username)

# ==============================================================================
# 4. 主程序入口区
# ==============================================================================
def main():
    print("🚀 自动化任务启动 (双引擎破盾架构)...")
    
    accounts_str = os.environ.get("acount")
    if not accounts_str:
        print("⚠️ 未获取到名为 'acount' 的环境变量，请在 GitHub Secrets 里配置！")
        return

    account_list = accounts_str.split(',')
    print(f"📋 共检测到 {len(account_list)} 个待处理账号。")
    
    for item in account_list:
        item = item.strip()
        if ':' in item:
            parts = item.split(':', 1) 
            process_single_account(parts[0].strip(), parts[1].strip())
            
    print("\n🏁 所有列队任务执行完毕！")

if __name__ == "__main__":
    main()
