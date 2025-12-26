from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

def search_comprehensive(query):
    try:
        with sync_playwright() as p:
            # Cấu hình tối ưu cho môi trường Docker/Render
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage', 
                    '--disable-gpu',
                    '--no-zygote',
                    '--single-process'
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # 1. Tìm thông tin tổng hợp
            search_url = f"https://www.google.com/search?q={query}+lịch+sử+văn+hoá+ẩm+thực+đặc+sản+vietnam&hl=vi"
            page.goto(search_url, timeout=30000)
            
            snippets = page.evaluate('''() => {
                const elements = Array.from(document.querySelectorAll('div.VwiC3b')).slice(0, 4);
                return elements.map(el => el.innerText).join(' | ');
            }''')
            
            # 2. Tìm hình ảnh
            page.goto(f"https://www.google.com/search?q={query}+cảnh+đẹp+du+lịch+vietnam&tbm=isch&hl=vi", timeout=30000)
            imgs = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img'))
                    .slice(2, 7)
                    .map(i => i.src)
                    .filter(s => s && s.startsWith('http'));
            }''')
            
            browser.close()
            
            yt_link = f"https://www.youtube.com/results?search_query=du+lich+{query.replace(' ', '+')}"
            return {"context": snippets, "imgs": imgs, "yt": yt_link}
            
    except Exception as e:
        print(f"Lỗi Playwright: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_msg = request.json.get('msg', '')
    if not user_msg:
        return jsonify({"text": "Bạn muốn hỏi gì về địa điểm này?", "images": [], "youtube": "", "suggestions": []})

    data = search_comprehensive(user_msg)
    
    if not data or not data['context']:
        return jsonify({
            "text": "🤖 Hệ thống đang khởi động hoặc bị giới hạn tài nguyên. Vui lòng thử lại sau vài giây!",
            "images": [],
            "youtube": "",
            "suggestions": ["Thử lại", f"Thời tiết tại {user_msg}"]
        })

    parts = data['context'].split('|')
    history = parts[0] if len(parts) > 0 else "Đang cập nhật dữ liệu lịch sử..."
    culture = parts[1] if len(parts) > 1 else "Đang cập nhật nét đẹp văn hóa..."
    cuisine = parts[2] if len(parts) > 2 else "Đang cập nhật đặc sản vùng miền..."

    html_res = f"""
    <div style='line-height:1.6'>
        <h3 style='color:#0077b6; border-bottom:2px solid #00b4d8; padding-bottom:5px'>🌟 THÔNG TIN: {user_msg.upper()}</h3>
        <p><b>📜 Lịch sử:</b> {history}</p>
        <p><b>🏛️ Văn hóa:</b> {culture}</p>
        <p><b>🍲 Ẩm thực:</b> {cuisine}</p>
    </div>
    """
    
    suggestions = [
        f"Món ngon tại {user_msg}?",
        f"Tour du lịch {user_msg}",
        f"Ảnh đẹp {user_msg}"
    ]
    
    return jsonify({
        "text": html_res,
        "images": data['imgs'],
        "youtube": data['yt'],
        "suggestions": suggestions
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
