from flask import Flask, render_template, request, jsonify
from duckduckgo_search import DDGS
import os

app = Flask(__name__)

def get_real_data(query):
    try:
        results = {"desc": "", "images": [], "videos": []}
        with DDGS() as ddgs:
            # 1. Lấy thông tin văn hóa, lịch sử, ẩm thực thực tế
            # Tìm kiếm cụ thể để lấy đoạn text dài và chất lượng
            search_str = f"{query} thông tin lịch sử văn hóa ẩm thực đặc sản chi tiết"
            texts = list(ddgs.text(search_str, region='vn-vi', max_results=4))
            
            combined_text = ""
            for t in texts:
                combined_text += f"📍 {t['body']}<br><br>"
            results["desc"] = combined_text

            # 2. Lấy danh sách ảnh thực tế
            imgs = list(ddgs.images(f"địa danh {query} du lịch đẹp", region='vn-vi', max_results=6))
            results["images"] = [i['image'] for i in imgs if i['image'].startswith('http')]

            # 3. Lấy link video review thực tế
            vids = list(ddgs.videos(f"review du lịch {query} thực tế", region='vn-vi', max_results=3))
            results["videos"] = [{"title": v['title'], "url": v['content']} for v in vids]

        return results
    except Exception as e:
        print(f"Lỗi tìm dữ liệu: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('msg', '')
    if not user_input:
        return jsonify({"text": "Bạn muốn khám phá địa điểm nào?"})

    # Gọi hàm lấy dữ liệu thật
    data = get_real_data(user_input)

    if not data or not data['desc']:
        return jsonify({"text": "❌ Không tìm thấy dữ liệu thực tế. Vui lòng thử lại với tên địa danh chính xác hơn."})

    # Tạo giao diện nội dung đặc sắc
    video_section = "<h4>🎥 Video Review Thực Tế:</h4><ul style='list-style: none; padding: 0;'>"
    for v in data['videos']:
        video_section += f"<li style='margin-bottom:8px'>🔗 <a href='{v['url']}' target='_blank' style='color:#00b4d8;text-decoration:none;'><b>{v['title']}</b></a></li>"
    video_section += "</ul>"

    full_html = f"""
    <div style='text-align: left; animation: fadeIn 0.5s;'>
        <h2 style='color: #d62828; border-bottom: 2px solid #fcbf49; padding-bottom: 5px;'>🚩 KHÁM PHÁ: {user_input.upper()}</h2>
        <div style='background: #fff; border-left: 5px solid #003049; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
            {data['desc']}
        </div>
        <div style='margin-top: 20px;'>
            {video_section}
        </div>
    </div>
    """

    return jsonify({
        "text": full_html,
        "images": data['images'],
        "suggestions": [f"Món ngon tại {user_input}", f"Lịch trình đi {user_input}", f"Khách sạn ở {user_input}"]
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
