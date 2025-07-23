const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const CopyPlugin = require("copy-webpack-plugin");

// 匯出一個函式，這樣我們就可以接收環境變數
module.exports = (env, argv) => {
  // 判斷是否為生產模式 (當執行 build script 時，mode 會是 'production')
  const isProduction = argv.mode === "production";

  return {
    // 模式：由 webpack-cli 傳入 (development 或 production)
    mode: argv.mode,
    // 入口點
    entry: {
      main: "./src/sketch.js",
      show_case: "./src/show_case.js",
    },

    // 出口設定
    output: {
      // 動態設定 publicPath
      // 生產模式下使用 '/static/' 以配合 Flask
      // 開發模式下使用 '/' 以配合 webpack-dev-server
      publicPath: isProduction ? "/static/" : "/",
      // 打包後的檔名
      filename: "[name].bundle.js",
      // 輸出目錄
      path: path.resolve(__dirname, "static"),
      // 每次打包前清除輸出目錄
      clean: true,
    },
    plugins: [
      new HtmlWebpackPlugin({
        title: "p5.js with Flask & Webpack",
        template: "src/index.html",
        chunks: ["main"],
      }),
      new HtmlWebpackPlugin({
        title: "Show Case",
        filename: "show_case.html",
        template: "src/show_case.html",
        chunks: ["show_case"],
      }),
      new CopyPlugin({
        patterns: [{ from: "public/assets", to: "assets" }],
      }),
    ],
    // 開發伺服器設定
    devServer: {
      static: [{ directory: path.resolve(__dirname, "public") }],
      hot: true,
      proxy: [
        {
          context: ["/socket.io", "/static"],
          target: "http://127.0.0.1:5000",
          ws: true,
        },
      ],
      historyApiFallback: true,
      // Prevent attempting to serve the same files twice
      devMiddleware: {
        writeToDisk: false,
      },
    },
  };
};
