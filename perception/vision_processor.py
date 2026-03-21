import pyautogui
import base64
from io import BytesIO
from PIL import Image

def capture_screen() -> str:
    """截取屏幕并返回Base64编码的图像数据"""
    #1. 截取屏幕
    screenshot = pyautogui.screenshot()
    #2. 压缩节省Token
    buffered = BytesIO()
    screenshot.save(buffered, format="JPEG", quality=70)  # 调整质量参数以压缩图像
    #3. 转换为Base64编码
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_str

#封装调用工具
def cur_screen() -> str:
   """获取当前屏幕快照"""
   try:
       #存入Data文件夹下并传给LLM
       path = "data/cur_screenshot.jpg"
       pyautogui.screenshot(path)
       return (f"当前屏幕快照已保存到: {path}")
   except Exception as e:
       return f"截屏失败: {str(e)}"
   