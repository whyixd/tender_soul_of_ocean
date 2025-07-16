from flask import Flask, send_from_directory

# 建立 Flask app
# static_folder='static' 告訴 Flask 靜態檔案放在 'static' 這個資料夾
# 這與 webpack.config.js 的 output.path 一致
app = Flask(__name__, static_folder="static")


# 設定網站根目錄的路由
@app.route("/")
def index():
    # 回傳 'static' 資料夾中的 index.html
    # Flask 會自動處理後續對 bundle.js 的請求
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    # 啟動伺服器，host='0.0.0.0' 讓區域網路中的其他裝置也能訪問
    app.run(host="0.0.0.0", port=5000, debug=True)
