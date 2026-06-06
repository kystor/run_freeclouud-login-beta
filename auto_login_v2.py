import base64
import os
import re
import time

import ddddocr
from seleniumbase import SB


CONFIG = {
    "target_url": "https://run.freecloud.ltd/login",
    "username_selector": "#emailInp",
    "password_selector": "#emailPwdInp",
    "captcha_img_selector": "#allow_login_email_captcha",
    "captcha_input_selector": "#captcha_allow_login_email_captcha",
    "login_btn_selector": 'button[type="submit"]',
    "user_center_selector": 'a[href="clientarea"]',
    "sign_in_url": "https://run.freecloud.ltd/addons?_plugin=5&_controller=index&_action=index",
    "sign_in_btn_selector": 'button[onclick="showMathVerification()"]',
    "math_question_selector": "#mathQuestion",
    "math_input_selector": "#userAnswer",
    "verify_btn_selector": 'button[onclick="checkAnswer()"]',
    "popup_content_selector": ".layui-layer-content",
    "popup_confirm_btn_selector": ".layui-layer-btn0",
    "points_balance_selector": "div.alert-success span",
    "server_list_url": "https://run.freecloud.ltd/service?groupid=305",
    "server_checkbox_selector": ".row-checkbox",
    "list_renew_btn_selector": "#readBtn",
    "confirm_renew_btn_selector": ".xfSubmit",
    "order_pay_btn_selector": "#payamount",
    "modal_pay_btn_selector": "button.pay-now",
}

CF_INTERSTITIAL_KEYWORDS = (
    "Just a moment",
    "Verify you are human",
    "Checking your browser",
    "Checking if the site connection is secure",
    "Enable JavaScript and cookies to continue",
)
CF_HARD_BLOCK_KEYWORDS = (
    "Error 1005",
    "Access denied",
    "Sorry, you have been blocked",
    "You have been blocked",
)
TURNSTILE_SELECTORS = (
    '.cf-turnstile',
    'iframe[src*="challenges.cloudflare.com"]',
    'iframe[src*="turnstile"]',
    'input[name="cf-turnstile-response"]',
)
CF_CLEARANCE_COOKIE = "cf_clearance"

OCR = ddddocr.DdddOcr(show_ad=False)
os.makedirs("screenshots", exist_ok=True)


def log(message: str) -> None:
    print(message, flush=True)


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()) or "unknown"


def take_screenshot(sb, step_name: str, username: str = "system") -> None:
    filepath = os.path.join(
        "screenshots",
        f"{sanitize_name(username)}_{sanitize_name(step_name)}.png",
    )
    try:
        sb.save_screenshot(filepath)
        log(f"    已保存截图: {filepath}")
    except Exception as exc:
        log(f"    截图失败: {exc}")


def first_env(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def page_source_and_title(sb) -> str:
    try:
        page_source = sb.get_page_source() or ""
    except Exception:
        page_source = ""
    try:
        title = sb.get_title() or ""
    except Exception:
        title = ""
    return f"{title}\n{page_source}"


def current_url_safe(sb) -> str:
    try:
        return sb.get_current_url() or ""
    except Exception:
        return ""


def title_safe(sb) -> str:
    try:
        return sb.get_title() or ""
    except Exception:
        return ""


def get_cookie_value(sb, cookie_name: str) -> str:
    try:
        cookie = sb.driver.get_cookie(cookie_name)
        if cookie and cookie.get("value"):
            return str(cookie["value"]).strip()
    except Exception:
        pass

    try:
        for cookie in sb.driver.get_cookies():
            if cookie.get("name") == cookie_name and cookie.get("value"):
                return str(cookie["value"]).strip()
    except Exception:
        pass

    return ""


def has_cf_clearance(sb) -> bool:
    return bool(get_cookie_value(sb, CF_CLEARANCE_COOKIE))


def get_turnstile_token(sb) -> str:
    try:
        if sb.is_element_present('input[name="cf-turnstile-response"]'):
            token = sb.get_attribute('input[name="cf-turnstile-response"]', "value")
            if token and len(token.strip()) > 20:
                return token.strip()
    except Exception:
        pass
    return ""


def has_turnstile_widget(sb) -> bool:
    for selector in TURNSTILE_SELECTORS:
        try:
            if sb.is_element_present(selector):
                return True
        except Exception:
            continue
    return False


def is_hard_blocked(sb) -> bool:
    content = page_source_and_title(sb)
    return any(keyword in content for keyword in CF_HARD_BLOCK_KEYWORDS)


def is_cloudflare_interstitial(sb) -> bool:
    content = page_source_and_title(sb)
    if any(keyword in content for keyword in CF_INTERSTITIAL_KEYWORDS):
        return True

    try:
        title = (sb.get_title() or "").lower()
        if "just a moment" in title or "attention required" in title:
            return True
    except Exception:
        pass

    try:
        body_length = sb.execute_script(
            "return document.body ? document.body.innerText.length : 0;"
        )
        page_source = sb.get_page_source() or ""
        if body_length is not None and body_length < 200 and "challenges.cloudflare.com" in page_source:
            return True
    except Exception:
        pass

    return False


def log_cf_state(sb, label: str) -> None:
    try:
        token = get_turnstile_token(sb)
        log(
            "    [CF状态] "
            f"{label} | "
            f"url={current_url_safe(sb)} | "
            f"title={title_safe(sb)} | "
            f"hard_block={is_hard_blocked(sb)} | "
            f"interstitial={is_cloudflare_interstitial(sb)} | "
            f"turnstile={has_turnstile_widget(sb)} | "
            f"token={'yes' if token else 'no'} | "
            f"cf_clearance={'yes' if has_cf_clearance(sb) else 'no'}"
        )
    except Exception as exc:
        log(f"    [CF状态] {label} | 读取失败: {exc}")


def accept_cookie_banner(sb) -> None:
    selectors = (
        'button[data-cky-tag="accept-button"]',
        'button[id*="accept"]',
        'button[class*="accept"]',
    )
    for selector in selectors:
        try:
            if sb.is_element_visible(selector):
                sb.click(selector)
                time.sleep(1)
                return
        except Exception:
            continue


def scroll_to_turnstile(sb) -> None:
    try:
        sb.execute_script(
            """
            const target =
                document.querySelector('.cf-turnstile') ||
                document.querySelector('iframe[src*="challenges.cloudflare.com"]') ||
                document.querySelector('iframe[src*="turnstile"]');
            if (target) {
                target.scrollIntoView({behavior: 'smooth', block: 'center'});
            }
            """
        )
    except Exception:
        pass


def wait_for_turnstile_result(sb, seconds: int) -> bool:
    for _ in range(seconds):
        if has_cf_clearance(sb):
            return True
        if get_turnstile_token(sb):
            return True
        if not has_turnstile_widget(sb) and not is_cloudflare_interstitial(sb):
            return True
        time.sleep(1)
    return False


def handle_turnstile_verification(sb, max_click_attempts: int = 3) -> bool:
    accept_cookie_banner(sb)
    scroll_to_turnstile(sb)
    time.sleep(2)
    start_url = current_url_safe(sb)

    if has_cf_clearance(sb):
        log("    已检测到 cf_clearance Cookie。")
        return True

    if get_turnstile_token(sb):
        log("    已检测到 Turnstile Token。")
        return True

    detected = False
    for _ in range(15):
        if has_turnstile_widget(sb):
            detected = True
            break
        if not is_cloudflare_interstitial(sb):
            return True
        time.sleep(1)

    if not detected:
        if is_cloudflare_interstitial(sb):
            log("    页面仍处于 Cloudflare 验证态。")
            return False
        log("    未检测到 Turnstile，继续后续流程。")
        return True

    log("    检测到 Turnstile，开始执行拟人点击。")
    for attempt in range(1, max_click_attempts + 1):
        log(f"      第 {attempt}/{max_click_attempts} 次点击验证。")
        scroll_to_turnstile(sb)
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass

        if wait_for_turnstile_result(sb, 20):
            if has_cf_clearance(sb):
                log("      已拿到 cf_clearance Cookie。")
            elif get_turnstile_token(sb):
                log("      已拿到 Turnstile Token。")
            elif current_url_safe(sb) != start_url:
                log("      页面地址已变化，疑似 Cloudflare 已放行。")
            else:
                log("      Turnstile 已放行。")
            return True

    log("    主动点击未通过，继续等待页面自行放行。")
    if wait_for_turnstile_result(sb, 60):
        if has_cf_clearance(sb):
            log("    等待后已拿到 cf_clearance Cookie。")
        return True
    return False


def bypass_cloudflare_interstitial(sb, max_attempts: int = 4) -> bool:
    log("    检测到 Cloudflare 盾，开始尝试放行。")
    for attempt in range(1, max_attempts + 1):
        log(f"      第 {attempt}/{max_attempts} 次尝试。")
        accept_cookie_banner(sb)
        scroll_to_turnstile(sb)
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass
        time.sleep(6)
        if not is_cloudflare_interstitial(sb):
            log("      Cloudflare 盾已放行。")
            return True
        if handle_turnstile_verification(sb):
            if has_cf_clearance(sb) or not is_cloudflare_interstitial(sb):
                log("      Cloudflare 验证已通过。")
                return True
        time.sleep(3)
    return False


def ensure_cloudflare_passed(sb, username: str, stage_name: str) -> bool:
    if is_hard_blocked(sb):
        log("    当前节点已被 Cloudflare 硬拦截。")
        log_cf_state(sb, f"{stage_name}_hard_block")
        take_screenshot(sb, f"{stage_name}_hard_block", username)
        return False

    if is_cloudflare_interstitial(sb):
        if not bypass_cloudflare_interstitial(sb):
            log("    Cloudflare 盾未能放行。")
            log_cf_state(sb, f"{stage_name}_interstitial_failed")
            take_screenshot(sb, f"{stage_name}_interstitial_failed", username)
            return False

    if has_turnstile_widget(sb) or is_cloudflare_interstitial(sb):
        if not handle_turnstile_verification(sb):
            log_cf_state(sb, f"{stage_name}_turnstile_failed")
            take_screenshot(sb, f"{stage_name}_turnstile_failed", username)
            return False

    if is_hard_blocked(sb) or is_cloudflare_interstitial(sb):
        log_cf_state(sb, f"{stage_name}_still_blocked")
        take_screenshot(sb, f"{stage_name}_still_blocked", username)
        return False

    log_cf_state(sb, f"{stage_name}_passed")
    return True


def open_page_with_cf_retry(
    sb,
    url: str,
    username: str,
    stage_name: str,
    max_attempts: int = 2,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        log(f"    打开 {stage_name}，第 {attempt}/{max_attempts} 次尝试。")
        sb.uc_open_with_reconnect(url, reconnect_time=8)
        time.sleep(4)
        if ensure_cloudflare_passed(sb, username, stage_name):
            return True
        time.sleep(5)
    return False


def read_balance_value(sb) -> float:
    balance_text = sb.get_text(CONFIG["points_balance_selector"])
    match = re.search(r"(\d+(?:\.\d+)?)", balance_text)
    if not match:
        raise ValueError(f"未从文本中读取到积分余额: {balance_text}")
    return float(match.group(1))


def solve_login_captcha(sb) -> str:
    for captcha_attempt in range(1, 11):
        sb.wait_for_element(CONFIG["captcha_img_selector"], timeout=10)
        img_src = sb.get_attribute(CONFIG["captcha_img_selector"], "src")
        if not img_src or "base64," not in img_src:
            log("      验证码图片不可用。")
            return ""

        try:
            base64_data = img_src.split(",", 1)[1]
            img_bytes = base64.b64decode(base64_data)
            captcha_text = OCR.classification(img_bytes).strip()
        except Exception as exc:
            log(f"      验证码识别失败: {exc}")
            captcha_text = ""

        if captcha_text.isdigit():
            log(f"      验证码识别成功: {captcha_text}")
            return captcha_text

        log(f"      第 {captcha_attempt}/10 次识别失败，刷新验证码。")
        try:
            sb.click(CONFIG["captcha_img_selector"])
        except Exception:
            pass
        time.sleep(2)

    return ""


def try_login(sb, username: str, password: str) -> bool:
    for login_attempt in range(1, 3):
        log(f"    开始第 {login_attempt}/2 次登录尝试。")

        if not ensure_cloudflare_passed(sb, username, f"login_attempt_{login_attempt}"):
            return False

        captcha_text = solve_login_captcha(sb)
        if not captcha_text:
            log("    登录验证码无法识别。")
            return False

        sb.clear(CONFIG["username_selector"])
        sb.type(CONFIG["username_selector"], username)
        sb.clear(CONFIG["password_selector"])
        sb.type(CONFIG["password_selector"], password)
        sb.clear(CONFIG["captcha_input_selector"])
        sb.type(CONFIG["captcha_input_selector"], captcha_text)
        sb.click(CONFIG["login_btn_selector"])
        time.sleep(5)

        if sb.is_element_present(CONFIG["user_center_selector"]):
            log(f"    登录成功，当前标题: {title_safe(sb)}")
            return True

        if is_hard_blocked(sb):
            log("    登录后被 Cloudflare 硬拦截。")
            take_screenshot(sb, f"login_hard_block_{login_attempt}", username)
            return False

        if is_cloudflare_interstitial(sb) or has_turnstile_widget(sb):
            log("    提交后再次触发了 Cloudflare 验证。")
            if ensure_cloudflare_passed(sb, username, f"login_post_submit_{login_attempt}"):
                time.sleep(2)
                if sb.is_element_present(CONFIG["user_center_selector"]):
                    log("    Cloudflare 放行后已登录成功。")
                    return True

        log("    当前登录未成功，刷新页面准备重试。")
        sb.refresh()
        time.sleep(3)

    return False


def solve_math_question(question_text: str):
    expression = question_text.replace("请计算：", "").replace("=", "").strip()
    expression = re.sub(r"[^0-9+\-*/(). ]+", "", expression)
    if not expression or not re.fullmatch(r"[0-9+\-*/(). ]+", expression):
        return None

    try:
        result = eval(expression, {"__builtins__": {}}, {})
    except Exception:
        return None

    if isinstance(result, float):
        if not result.is_integer():
            return None
        return int(result)
    if isinstance(result, int):
        return result
    return None


def run_daily_sign_in(sb, username: str) -> float:
    log(">>> 开始执行每日签到流程")
    if not open_page_with_cf_retry(sb, CONFIG["sign_in_url"], username, "sign_in_page"):
        log("    签到页 Cloudflare 验证未通过。")
        return 0.0

    take_screenshot(sb, "sign_in_page", username)
    balance_value = 0.0

    for attempt in range(1, 6):
        log(f"    第 {attempt}/5 次签到尝试。")
        sb.click(CONFIG["sign_in_btn_selector"])
        time.sleep(2)

        question_text = sb.get_text(CONFIG["math_question_selector"])
        answer = solve_math_question(question_text)
        if answer is None:
            log("    当前算式结果不是整数，刷新重试。")
            sb.refresh()
            time.sleep(3)
            continue

        log(f"    本次算式答案: {answer}")
        sb.clear(CONFIG["math_input_selector"])
        sb.type(CONFIG["math_input_selector"], str(answer))
        sb.click(CONFIG["verify_btn_selector"])

        sb.wait_for_element(CONFIG["popup_content_selector"], timeout=5)
        popup_msg = sb.get_text(CONFIG["popup_content_selector"])
        log(f"    签到弹窗提示: {popup_msg}")
        sb.click(CONFIG["popup_confirm_btn_selector"])
        time.sleep(2)

        sb.refresh()
        time.sleep(4)
        take_screenshot(sb, "sign_in_result", username)

        try:
            balance_value = read_balance_value(sb)
            log(f"    当前积分余额: {balance_value}")
        except Exception as exc:
            log(f"    读取积分余额失败: {exc}")

        return balance_value

    log("    连续 5 次签到尝试都未成功。")
    return balance_value


def renew_server_if_needed(sb, username: str, balance_value: float) -> None:
    if balance_value <= 2:
        log(f">>> 当前积分不足以续费: {balance_value}")
        return

    log(f">>> 当前积分足够续费: {balance_value}")
    if not open_page_with_cf_retry(sb, CONFIG["server_list_url"], username, "server_list_page"):
        log("    服务器列表页 Cloudflare 验证未通过。")
        return

    take_screenshot(sb, "server_list_page", username)

    if not sb.is_element_present(CONFIG["server_checkbox_selector"]):
        log("    当前账号下未检测到可续费服务器。")
        return

    sb.click(CONFIG["server_checkbox_selector"])
    sb.js_click(CONFIG["list_renew_btn_selector"])
    time.sleep(4)

    sb.wait_for_element_visible(CONFIG["confirm_renew_btn_selector"], timeout=10)
    sb.scroll_to(CONFIG["confirm_renew_btn_selector"])
    sb.click(CONFIG["confirm_renew_btn_selector"])
    time.sleep(5)

    sb.wait_for_element(CONFIG["order_pay_btn_selector"], timeout=15)
    sb.js_click(CONFIG["order_pay_btn_selector"])
    sb.wait_for_element(CONFIG["modal_pay_btn_selector"], timeout=10)
    sb.js_click(CONFIG["modal_pay_btn_selector"])
    log("    已确认支付，等待系统处理。")
    time.sleep(8)

    take_screenshot(sb, "payment_result", username)

    try:
        for item in sb.find_elements("section.text-gray p"):
            if "到期时间" in item.text:
                log(f"    续费成功: {item.text}")
                break
    except Exception:
        pass

    log(">>> 续费完成，返回签到页读取最新积分")
    sb.open(CONFIG["sign_in_url"])
    time.sleep(4)
    take_screenshot(sb, "sign_in_after_renew", username)

    try:
        final_balance = read_balance_value(sb)
        log(f"    续费后积分余额: {final_balance}")
    except Exception as exc:
        log(f"    读取续费后积分失败: {exc}")


def process_single_account(username: str, password: str) -> None:
    log("\n==========================================")
    log(f"开始处理账号: {username}")
    log("==========================================")

    proxy_value = first_env("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
    chromium_args = [
        "--disable-blink-features=AutomationControlled",
        "--window-size=1920,1080",
        "--lang=en-US",
        "--disable-quic",
    ]
    if proxy_value:
        chromium_args.append(f"--proxy-server={proxy_value}")
        log(f"使用浏览器代理: {proxy_value}")
    else:
        log("未检测到浏览器代理，当前将直接访问。")

    with SB(
        uc=True,
        test=True,
        locale="en",
        headless=False,
        proxy=proxy_value or None,
        chromium_arg=",".join(chromium_args),
    ) as sb:
        try:
            if not open_page_with_cf_retry(sb, CONFIG["target_url"], username, "login_page"):
                log("    登录页 Cloudflare 验证未通过，跳过当前账号。")
                return

            take_screenshot(sb, "login_page_ready", username)

            if not try_login(sb, username, password):
                log("    登录在重试后仍失败，跳过当前账号。")
                take_screenshot(sb, "login_failed", username)
                return

            take_screenshot(sb, "login_success", username)
            balance_value = run_daily_sign_in(sb, username)
            renew_server_if_needed(sb, username, balance_value)

        except Exception as exc:
            log(f"    账号处理过程中出现异常: {exc}")
            take_screenshot(sb, "account_error", username)


def main() -> None:
    log("自动化任务已启动。")
    accounts_str = os.environ.get("acount", "").strip()
    if not accounts_str:
        log("环境变量 acount 为空。")
        return

    account_list = [item.strip() for item in accounts_str.split(",") if item.strip()]
    log(f"检测到 {len(account_list)} 个账号。")

    for item in account_list:
        if ":" not in item:
            log(f"跳过格式错误的账号配置: {item}")
            continue
        username, password = item.split(":", 1)
        process_single_account(username.strip(), password.strip())

    log("\n所有账号任务执行完成。")


if __name__ == "__main__":
    main()
