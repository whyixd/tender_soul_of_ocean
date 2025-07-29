import p5, { toggleClass } from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";
// FES 禁用程式碼可以保留，以備生產環境之需
// if (process.env.NODE_ENV === "production") {
//   window.p5.disableFriendlyErrors = true;
// }
if (process.env.NODE_ENV === "production") {
  p5.disableFriendlyErrors = true;
}
const sketch = (p) => {
  let socket;
  let shape;
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

  let lightCornerPos = [-38.9, -83.4];
  let lightColor = [255, 150, 6];
  let lightValues = [];
  let lightRawData = { matrix: [] };
  for (let i = 0; i < 8; i++) {
    let newRow = [];

    for (let j = 0; j < 16; j++) {
      newRow.push(0);
    }
    lightValues.push(newRow);
    lightRawData.matrix.push(newRow.slice(0)); // deep copy
  }
  const settings = {
    background: "#112233",
    sinOffset: 1.86,
    sinLength: 0.32,
    sinScale: 7.03,
    sinYOffset: 0,
    useEase: true,
    showControlPoints: false,
  };
  let pos = { x: 0, y: 0, z: 0 };
  let posIncrement = 0.1;
  let tsooParam = {
    people_count_max: 100,
    wind_speed: 0,
    wind_speed_max: 10,
    area_people_count: 0,
    people_natrual_weight: 0,
    people_natrual_weight_level: 0,
    people_natrual_weight_level_threshold: 0.5,
    wind_angle: 0,
    effect_vector: 0,
    effect_angle: 0,
  };
  // let sinOffset = 0;
  // let sinLength = 1;
  // let sinScale = 1;
  // let sinYOffset = 0;
  p.setup = async () => {
    const modelPath =
      process.env.NODE_ENV === "production"
        ? "/static/assets/20250616_linz.obj" // 生產環境路徑 (build 後)
        : "assets/20250616_linz.obj"; // 開發環境路徑 (npm start)

    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);
    p.angleMode(p.RADIANS);
    const gui = new GUI();

    gui.addColor(settings, "background").name("背景顏色");
    gui
      .add(settings, "sinOffset", 0, 10)
      .name("正弦波偏移")
      .step(0.01)
      .onChange((value) => {
        sinOffset = value;
      });
    gui
      .add(settings, "sinLength", 0, 5)
      .name("正弦波振幅")
      .step(0.01)
      .onChange((value) => {
        sinLength = value;
      });
    gui
      .add(settings, "sinScale", 0, 100)
      .name("正弦波縮放")
      .step(0.01)
      .onChange((value) => {
        sinScale = value;
      });
    gui
      .add(settings, "sinYOffset", -10, 10)
      .name("正弦波Y偏移")
      .step(0.01)
      .onChange((value) => {
        sinYOffset = value;
      });
    gui.add(settings, "useEase").name("使用Ease函數利於顯示");
    gui.add(settings, "showControlPoints").name("顯示控制點");
    const matrixFolder = gui.addFolder("8x16 Matrix (Display Only)");
    for (let i = 0; i < 8; i++) {
      const rowFolder = matrixFolder.addFolder(`Row ${i}`);

      // 🔥 關鍵點 1: 預設關閉資料夾，保持 UI 乾淨
      rowFolder.close();

      for (let j = 0; j < 16; j++) {
        const controller = rowFolder
          .add(lightRawData.matrix[i], j)
          .name(`Col ${i * 16 + j + 1}`)
          .listen();

        // 🔥 關鍵點 2: 禁用控制器，使其不可互動
        controller.disable();
      }
    }
    const tsooParamGui = new GUI({
      container: document.body,
      width: 300,
    });

    // 設置 GUI 標題
    tsooParamGui.title("Tsoo Param");

    // 設置 GUI 位置到左上角
    tsooParamGui.domElement.style.position = "absolute";
    tsooParamGui.domElement.style.top = "10px";
    tsooParamGui.domElement.style.left = "10px";

    tsooParamGui
      .add(tsooParam, "people_count_max")
      .name("人數計數最大值")
      .listen();
    tsooParamGui
      .add(tsooParam, "wind_speed", 0, 10)
      .name("風速")
      .step(0.01)
      .listen();
    tsooParamGui
      .add(tsooParam, "wind_speed_max", 0, 10)
      .name("風速最大值")
      .step(0.01)
      .listen();
    tsooParamGui
      .add(tsooParam, "area_people_count")
      .name("區域人數計數")

      .listen();
    tsooParamGui
      .add(tsooParam, "people_natrual_weight", 0, 1)
      .name("人數自然權重")
      .step(0.01)
      .listen();
    tsooParamGui
      .add(tsooParam, "people_natrual_weight_level", {
        Low: 0,
        Medium: 1,
        High: 2,
      })
      .name("人數自然權重級別")
      .listen();
    tsooParamGui
      .add(tsooParam, "people_natrual_weight_level_threshold")
      .name("人數自然閾值")
      .listen();
    tsooParamGui.add(tsooParam, "wind_angle").name("風向角度").listen();
    tsooParamGui.add(tsooParam, "effect_vector").name("效果向量").listen();
    tsooParamGui.add(tsooParam, "effect_angle").name("效果角度").listen();

    if (process.env.NODE_ENV === "production") {
      socket = io();
    } else {
      socket = io("http://localhost:5000");
    }
    socket.on("connect", () => {
      console.log("✅ Connected to Socket.IO server!");
      console.log("Socket ID:", socket.id);
      settings.isConnected = true;
    });
    socket.on("disconnect", () => {
      console.log("❌ Disconnected from Socket.IO server!");
      settings.isConnected = false;
    });
    socket.on("tsoo_param", (data) => {
      // console.log("Received tsoo_param:", data);
      tsooParam["people_count_max"] = data.people_count_max;
      tsooParam["wind_speed"] = data.wind_speed;
      tsooParam["area_people_count"] = data.area_people_count;
      tsooParam["people_natrual_weight"] = data.people_natrual_weight;
      tsooParam["people_natrual_weight_level"] =
        data.people_natrual_weight_level;
      tsooParam["people_natrual_weight_level_threshold"] =
        data.people_natrual_weight_level_threshold;
      tsooParam["wind_angle"] = roundToTwoDecimalPlaces(data.wind_angle);
      tsooParam["effect_vector"] = [
        roundToTwoDecimalPlaces(data.effect_vector[0]),
        roundToTwoDecimalPlaces(data.effect_vector[1]),
      ];
      // tsooParam["effect_vector"] = data.effect_vector;
      tsooParam["effect_angle"] = data.effect_angle;
      // console.log("Received tsoo_param:", tsooParam);
    });

    socket.on("server_message", (data) => {
      console.log("📬 Message from server:", data.message);
      // 收到伺服器訊息時，隨機改變背景顏色來測試
      settings.background = p.color(
        p.random(255),
        p.random(255),
        p.random(255)
      );
    });
    socket.on("dmx_data", (data) => {
      // 更新 lightValues
      for (let i = 0; i < lightValues.length; i++) {
        for (let j = 0; j < lightValues[i].length; j++) {
          lightValues[i][j] = data.value[i * 16 + j] / 255; // 假設數據是 0-255 範圍
          lightRawData.matrix[i][j] = data.value[i * 16 + j]; // 更新原始數據
        }
      }
    });
    console.log("Setup 執行中... 開始等待模型載入。");

    try {
      shape = await p.loadModel(modelPath, true);
      console.log("✅ 模型載入成功!", shape);
    } catch (error) {
      console.error("❌ 模型載入失敗:", error);
    }

    p.camera(400, -400, 500);
  };

  p.draw = () => {
    p.background(settings.background);
    p.orbitControl();
    p.lights();
    p.noStroke();
    let orthoScale = 8;
    p.ortho(
      -p.width / orthoScale,
      p.width / orthoScale,
      -p.height / orthoScale,
      p.height / orthoScale,
      0,
      1000
    );
    p.rotateX(p.PI / 2);
    // p.rotateZ(-p.PI / 2);
    if (shape) {
      p.scale(1, -1, 1);
      p.model(shape);
    }
    if (settings.showControlPoints) {
      p.push();
      p.translate(
        lightCornerPos[0] * tsooParam["effect_vector"][1] * -1,
        lightCornerPos[1] * tsooParam["effect_vector"][0],
        0
      );
      p.fill(255, 0, 0);
      p.sphere(1);
      p.pop();
      // create light cylinder
    }
    p.push();
    p.fill(255, 0, 255);
    p.rotateX(p.PI / 2);
    for (let i = 0; i < startPosition.length; i++) {
      p.translate(startPosition[i].x, startPosition[i].y, startPosition[i].z);
      let firstColumnValus = lightValues[startPosition.length - 1 - i][0];
      firstColumnValus = settings.useEase
        ? easeOutExpo(firstColumnValus)
        : firstColumnValus;

      p.fill(
        firstColumnValus * lightColor[0],
        firstColumnValus * lightColor[1],
        firstColumnValus * lightColor[2]
      );
      p.cylinder(0.5, 25.6);
      for (let j = 1; j < 16; j++) {
        // 使用 sinParams[i]
        p.translate(
          0,
          p.sin(j * sinParams[i].sinLength + sinParams[i].sinOffset) *
            sinParams[i].sinScale +
            sinParams[i].sinYOffset,
          11.12
        );
        let lightValue = lightValues[startPosition.length - 1 - i][j];

        lightValue = settings.useEase ? easeOutExpo(lightValue) : lightValue;
        // 使用 light
        p.fill(
          lightValue * lightColor[0],
          lightValue * lightColor[1],
          lightValue * lightColor[2]
        );
        print;
        p.cylinder(0.5, 25.6);
      }
    }

    p.pop();
    // p.push();
    // p.fill(255);
    // p.rotateY(p.PI / 2);
    // p.square(0, 100, 100);
    // p.pop();
    if (p.keyIsPressed) {
      if (p.key === "a") {
        // A key
        pos.x -= posIncrement;
      }
      if (p.key === "d") {
        // D key
        pos.x += posIncrement;
      }
    }
    if (p.keyIsDown(p.LEFT_ARROW)) {
      pos.z -= posIncrement;
    }
    if (p.keyIsDown(p.RIGHT_ARROW)) {
      pos.z += posIncrement;
    }
    if (p.keyIsDown(p.DOWN_ARROW)) {
      pos.y -= posIncrement;
    }
    if (p.keyIsDown(p.UP_ARROW)) {
      pos.y += posIncrement;
    }
  };

  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
  p.keyReleased = () => {
    console.log(pos);
  };
};

// 啟動 p5 sketch
new p5(sketch);

function easeOutExpo(x) {
  return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
}
function roundToTwoDecimalPlaces(value) {
  return Math.round(value * 100) / 100;
}
