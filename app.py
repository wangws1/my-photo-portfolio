import os
import sqlite3
import datetime
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ExifTags

app = Flask(__name__)

# --- 配置 ---
UPLOAD_FOLDER = 'static/uploads'
DB_FILE = 'photo_db.db'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
WATERMARK_TEXT = "@MyName Photography"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 自动创建上传文件夹


# --- 数据库初始化函数 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 创建一个表：存ID、文件名、类别、日期、EXIF数据
    c.execute('''CREATE TABLE IF NOT EXISTS photos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  category TEXT,
                  upload_date TEXT,
                  exif_info TEXT)''')
    conn.commit()
    conn.close()


init_db()  # 启动时运行一次


# --- 辅助功能：处理图片 (压缩 + 水印 + EXIF) ---
def process_image(filepath, filename):
    img = Image.open(filepath)

    # 1. 读取 EXIF (简化版)
    exif_data = "No EXIF"
    try:
        exif = {ExifTags.TAGS[k]: v for k, v in img._getexif().items() if k in ExifTags.TAGS}
        # 提取关键信息
        model = exif.get('Model', 'Unknown Camera')
        f_number = f"f/{exif.get('FNumber', 0)}"
        exposure = f"{exif.get('ExposureTime', 0)}s"
        iso = f"ISO {exif.get('ISOSpeedRatings', 0)}"
        exif_data = f"{model} | {f_number} | {exposure} | {iso}"
    except:
        pass

    # 2. 添加水印
    draw = ImageDraw.Draw(img)
    # 这里简单地在右下角画字，为了效果好需要更复杂的计算，这里取巧
    w, h = img.size
    # 字体位置 (右下角)
    draw.text((w - 200, h - 50), WATERMARK_TEXT, fill=(255, 255, 255, 128))

    # 3. 压缩并保存
    # 转换为 RGB 避免报错，保存为 WebP 格式优化体积
    img = img.convert('RGB')
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img.save(save_path, 'WEBP', quality=80)  # 质量80%

    return exif_data


# --- 路由：主页 (展示画廊) ---
@app.route('/')
def index():
    category_filter = request.args.get('category')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if category_filter:
        c.execute("SELECT * FROM photos WHERE category = ? ORDER BY upload_date DESC", (category_filter,))
    else:
        c.execute("SELECT * FROM photos ORDER BY upload_date DESC")

    photos = c.fetchall()
    conn.close()
    return render_template('index.html', photos=photos)


# --- 路由：上传接口 ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return '没有文件'
    file = request.files['file']
    category = request.form.get('category')

    if file:
        filename = secure_filename(file.filename)
        # 临时保存原图
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_' + filename)
        file.save(temp_path)

        # 处理图片 (水印、压缩、提取EXIF)
        final_filename = os.path.splitext(filename)[0] + ".webp"
        exif_info = process_image(temp_path, final_filename)

        # 删除临时原图
        os.remove(temp_path)

        # 写入数据库
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute("INSERT INTO photos (filename, category, upload_date, exif_info) VALUES (?, ?, ?, ?)",
                  (final_filename, category, now, exif_info))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))
    return '上传失败'


# --- 路由：删除接口 ---
@app.route('/delete/<int:photo_id>')
def delete_photo(photo_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 先查文件名，删文件
    c.execute("SELECT filename FROM photos WHERE id = ?", (photo_id,))
    row = c.fetchone()
    if row:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row[0]))
        except:
            pass
        # 再删数据库记录
        c.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)