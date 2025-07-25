import p5 from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";

const sketch = (p) => {
  let gui;
  let socket;
  let scroll_dmx_data = [];
  const max_lines = 12; // 最大顯示行數
  let font; // 用於存放字體
  let dmx_data = [];
  let capture;

  let startPosition = [
    { x: -38.9, y: 9.3, z: -83.4 },
    { x: 11.2, y: 21.2, z: -166.7 },
    { x: 11.19, y: 3, z: -166.89 },
    { x: 11.1, y: -12.5, z: -167 },
    { x: 11, y: -23.1, z: -166.7 },
    { x: 10.9, y: -35.6, z: -166.6 },
    { x: 11.5, y: -41.6, z: -166.9 },
    { x: 10.8, y: -46.5, z: -166.7 },
  ];

  let sinParams = [
    { sinOffset: 1.92, sinLength: 0.31, sinScale: 7.68, sinYOffset: 0.13 },
    { sinOffset: 2.15, sinLength: 0.28, sinScale: 2.98, sinYOffset: 0.3 },
    { sinOffset: 5.44, sinLength: 0.12, sinScale: 0.56, sinYOffset: 0.26 },
    { sinOffset: 4.03, sinLength: 0.41, sinScale: 2.87, sinYOffset: 1.02 },
    { sinOffset: 4.76, sinLength: 0.32, sinScale: 5.39, sinYOffset: 0.76 },
    { sinOffset: 4.86, sinLength: 0.32, sinScale: 7.48, sinYOffset: 0.65 },
    { sinOffset: 4.43, sinLength: 0.36, sinScale: 7.21, sinYOffset: 1.99 },
    { sinOffset: 4.7, sinLength: 0.33, sinScale: 8.05, sinYOffset: 1.53 },
  ];

  p.setup = async () => {
    if (process.env.NODE_ENV === "production") {
      p5.disableFriendlyErrors = true;
    }
    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);
    try {
      font = await p.loadFont("assets/Roboto_Condensed-Light.ttf"); // 載入字體檔案
      p.textFont(font); // 設定字體
    } catch (e) {
      console.error("Font loading error:", e);
    }
    if (process.env.NODE_ENV === "production") {
      socket = io();
    } else {
      socket = io("http://localhost:5000");
    }

    socket.on("connect", () => {
      console.log("Connected to server");
    });

    socket.on("dmx_data", (data) => {
      const timestamp = new Date().toISOString(); // 生成 ISO 格式的時間碼
      dmx_data = data.value;
      scroll_dmx_data.push(
        `[${timestamp}] > RECEIVE..|..ENDPOINT(127.0.0.1:61373) OPCODE(DMX) SEQUENCE(0) PHYSICAL(0) UNIVERSE(0) DATA(` +
          data.value.toString() +
          ")\n"
      ); // 將接收到的資料加入陣列
      if (scroll_dmx_data.length > max_lines) {
        scroll_dmx_data.shift(); // 移除最舊的資料
      }
    });

    // p.camera(400, -400, 500);
    capture = p.createCapture(p.VIDEO);
    capture.hide();
    setInterval(() => {
      const timestamp = new Date().toISOString(); // 生成 ISO 格式的時間碼
      scroll_dmx_data.push(
        `[${timestamp}] > RECEIVE..|..NDPOINT(127.0.0.1:6454) OPCODE(POLL)\n`
      );
      if (scroll_dmx_data.length > max_lines) {
        scroll_dmx_data.shift(); // 移除最舊的資料
      }
    }, 3000);
  };
  p.draw = () => {
    p.background("#000000ff");
    p.textAlign(p.LEFT, p.TOP);
    p.textSize(3);
    p.orbitControl();
    p.ortho();
    p.image(capture, -p.width / 2, -p.height / 3, 400, 225);
    let orthoScale = 8;
    p.ortho(
      -p.width / orthoScale,
      p.width / orthoScale,
      -p.height / orthoScale,
      p.height / orthoScale,
      0,
      1000
    );
    // 繪製 DMX 資料，最新資料在最下方
    let y = -p.height / 6 + 80;
    for (let i = 0; i < scroll_dmx_data.length; i++) {
      let x = -p.width / 6 + 50;
      const line = scroll_dmx_data[i];

      // 分割字串並設置顏色
      const parts = line.split(
        /(RECEIVE|ENDPOINT|OPCODE|SEQUENCE|PHYSICAL|UNIVERSE|DATA|DMX)/
      );
      parts.forEach((part) => {
        if (part === "RECEIVE") {
          p.fill(0, 255, 0); // 綠色
        } else if (
          [
            "ENDPOINT",
            "OPCODE",
            "SEQUENCE",
            "PHYSICAL",
            "UNIVERSE",
            "DATA",
          ].includes(part)
        ) {
          p.fill(0, 255, 255); // 水藍色
        } else if (part === "DMX") {
          p.fill(255, 105, 180); // 桃紅色
        } else {
          p.fill(255); // 白色
        }
        p.text(part, x, y);
        x += p.textWidth(part); // 更新 x 座標
      });

      y += 6; // 每行文字的間距
    }
    p.rotateX(p.PI / 2);
    p.rotateZ(-p.PI / 2);
    p.push();
    p.noStroke();
    p.strokeWeight(0.1);
    p.fill(200);
    // 讓球體更靠近camera
    p.rotateY(-p.PI / 4);
    p.rotateX(p.PI / 2);
    p.translate(-500, 400, 0);
    p.rotateY(p.frameCount * 0.001);
    for (let i = 0; i < startPosition.length; i++) {
      p.translate(startPosition[i].x, startPosition[i].y, startPosition[i].z);
      p.box((dmx_data[i * 16] / 255) * 5);
      for (let j = 1; j < 16; j++) {
        // 使用 sinParams[i]
        p.translate(
          0,
          p.sin(j * sinParams[i].sinLength + sinParams[i].sinOffset) *
            sinParams[i].sinScale +
            sinParams[i].sinYOffset +
            p.random(0.05),
          11.12
        );
        p.box((dmx_data[i * 16 + j] / 255) * 5);
      }
    }
  };

  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
};

new p5(sketch);
