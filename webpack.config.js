const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");

module.exports = {
  // 模式：production 會進行優化，development 則著重開發速度
  mode: "production",
  // 入口點
  entry: "./src/sketch.js",

  // 出口設定
  output: {
    // 公共路徑，這裡設定為 /static/，這樣在 HTML 中引用資源時會自動加上這個前綴
    publicPath: "/static/",
    // 打包後的檔名
    filename: "bundle.js",
    // 輸出目錄，必須是絕對路徑
    // __dirname 是 Node.js 變數，代表當前檔案所在目錄
    path: path.resolve(__dirname, "static"),
    // 每次打包前清除輸出目錄
    clean: true,
  },
  plugins: [
    new HtmlWebpackPlugin({
      // 以這個檔案為模板，自動生成 index.html 到輸出目錄
      // 它會自動幫你加上 <script src="bundle.js"></script>
      title: "p5.js with Flask & Webpack",
      template: "src/index.html", // 我們需要手動建立這個模板
    }),
  ],
  // 開發伺服器設定
  devServer: {
    static: [
      { directory: path.resolve(__dirname, "static") },
      { directory: path.resolve(__dirname, "public") },
    ], // 伺服器根目錄
    hot: true, // 啟用熱重載
  },
};
