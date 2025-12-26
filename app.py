from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

def search_comprehensive(query):
    try:
        with sync_playwright() as p:
            # Render lưu browser ở đường dẫn cụ thể, ta sẽ để Playwright tự tìm 
            # nhưng thêm cấu hình tối giản nhất để tránh treo RAM
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--single-process'
                ]
            )
            context = browser.new_context(user_agent="Mozilla/5.0")
            page = context.new_page()
            
            # Tăng timeout lên 60s vì gói Free của Render khá chậm
            search_url = f"https://www.google.com/search?q={query}+lịch+sử+văn+hoá+ẩm+thực+vietnam&hl=vi"
            page.goto(search_url, timeout=60000)
            
            # Đợi một chút để nội dung kịp load
            page.wait_for_timeout(2000) 

            snippets = page.evaluate('''() => {
                const elements = Array.from(document.querySelectorAll('div.VwiC3b')).slice(0, 3);
                return elements.map(el => el.innerText).join(' | ');
            }''')
            
            # Lấy ảnh
            page.goto(f"https://www.google.com/search?q={query}+du+lich+vietnam&tbm=isch", timeout=60000)
            page.wait_for_timeout(2000)
            imgs = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img'))
                    .slice(2, 6)
                    .map(i => i.src)
                    .filter(s => s && s.startsWith('http'));
            }''')
            
            browser.close()
            return {"context": snippets, "imgs": imgs}
            
    except Exception as e:
        print(f"Lỗi thực thi: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_msg = request.json.get('msg', '')
    data = search_comprehensive(user_msg)
    
    if not data or not data['context']:
        # Nếu lỗi, thử trả về một câu trả lời mặc định thay vì báo lỗi tài nguyên
        return jsonify({
            "text": f"🤖 Tôi tìm thấy {user_msg} là một địa điểm tuyệt vời tại Việt Nam. Tuy nhiên kết nối dữ liệu chi tiết đang chậm, bạn hãy thử lại sau vài giây hoặc hỏi về địa điểm khác nhé!",
            "images": [],
            "youtube": f"https://www.youtube.com/results?search_query={user_msg}",
            "suggestions": ["Hà Nội", "Hội An", "Đà Nẵng"]
        })

    parts = data['context'].split('|')
    html_res = f"""
    <div style='line-height:1.6'>
        <h3 style='color:#0077b6;'>📍 {user_msg.upper()}</h3>
        <p><b>Thông tin:</b> {parts[0] if len(parts)>0 else 'Đang cập nhật...'}</p>
        <p><b>Chi tiết:</b> {parts[1] if len(parts)>1 else 'Đang nghiên cứu thêm...'}</p>
    </div>
    """
    return jsonify({
        "text": html_res,
        "images": data['imgs'],
        "youtube": f"https://www.youtube.com/results?search_query={user_msg}",
        "suggestions": [f"Ẩm thực {user_msg}", f"Tour {user_msg}"]
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
