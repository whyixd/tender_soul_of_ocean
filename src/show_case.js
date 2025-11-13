import p5 from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";
function convertWindAngleToDirection(angle) {
  if (angle >= 337.5 || angle < 22.5) return "N";
  if (angle >= 22.5 && angle < 67.5) return "WE";
  if (angle >= 67.5 && angle < 112.5) return "W";
  if (angle >= 112.5 && angle < 157.5) return "WS";
  if (angle >= 157.5 && angle < 202.5) return "S";
  if (angle >= 202.5 && angle < 247.5) return "SE";
  if (angle >= 247.5 && angle < 292.5) return "SW";
  if (angle >= 292.5 && angle < 337.5) return "NW";

  return "N";
}
function drawAreaPeople(
  p,
  areaIndex,
  peopleRandomPos,
  targetAreaCircleSize,
  currentAreaCircleSize
) {
  let areaPoss = [
    [-200 * 1.5, -50 * 1.5],
    [80 * 1.5, -120 * 1.5],
    [200 * 1.5, 120 * 1.5],
    [-150 * 1.5, 80 * 1.5],
  ];
  let areaPos = areaPoss[areaIndex];
  let preAreaPos = areaPoss[areaIndex - 1] || areaPoss[areaPoss.length - 1];
  p.push();
  p.stroke(255);
  p.strokeWeight(0.03);
  p.line(preAreaPos[0], preAreaPos[1], areaPos[0], areaPos[1]);
  p.strokeWeight(0.08);
  p.translate(areaPos[0], areaPos[1], 0);
  p.textSize(5);
  p.fill(255);
  p.text(areaIndex, -2, -2);
  p.fill(255, 10);
  p.fill(255, 10);
  if (peopleRandomPos !== undefined) {
    let previousPoint = undefined;
    for (let i = 0; i < peopleRandomPos.length; i++) {
      for (let j = 0; j < peopleRandomPos[areaIndex].length; j++) {
        let x = peopleRandomPos[areaIndex][j].x + p.random(1, 3);
        let y = peopleRandomPos[areaIndex][j].y + p.random(1, 3);
        p.circle(x, y, 5);
        if (previousPoint !== undefined)
          p.line(previousPoint[0], previousPoint[1], x, y);
        previousPoint = [x, y];
      }
      targetAreaCircleSize[areaIndex] = peopleRandomPos[areaIndex].length * 10;
    }
    if (currentAreaCircleSize[areaIndex] !== targetAreaCircleSize[areaIndex]) {
      let gap =
        targetAreaCircleSize[areaIndex] - currentAreaCircleSize[areaIndex] > 0
          ? 1
          : -1;

      currentAreaCircleSize[areaIndex] += 2 * gap * p.random(0.5, 0.8);
    }
    p.circle(5, 0, currentAreaCircleSize[areaIndex]);
  }
  p.pop();
}
const sketch = (p) => {
  let gui;
  let socket;
  const max_lines = 54; // 最大顯示行數
  const LOG_TEXT_SIZE = 1.8;
  const LOG_TOKEN_REGEX =
    /(RECEIVE|ENDPOINT|OPCODE|SEQUENCE|PHYSICAL|UNIVERSE|DATA|DMX)/;
  const LOG_TOKEN_COLORS = {
    RECEIVE: [0, 255, 0],
    ENDPOINT: [0, 255, 255],
    OPCODE: [0, 255, 255],
    SEQUENCE: [0, 255, 255],
    PHYSICAL: [0, 255, 255],
    UNIVERSE: [0, 255, 255],
    DATA: [0, 255, 255],
    DMX: [255, 105, 180],
    DEFAULT: [0, 0, 0],
  };
  const scroll_dmx_data = new Array(max_lines);
  let logWriteIndex = 0;
  let logCount = 0;
  let font; // 用於存放字體
  let boldFont;
  let zh_font;
  let zh_boldFont;
  let barcodeFont;
  let logFont;
  let dmx_data = [];
  let tsooParam = {};
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
  let previousTsooParam = {};
  let peopleRandomPos = [];
  let targetAreaCircleSize = [0, 0, 0, 0];
  let currentAreaCircleSize = [0, 0, 0, 0];

  let location = {};
  p.setup = async () => {
    if (process.env.NODE_ENV === "production") {
      p5.disableFriendlyErrors = true;
    }
    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);
    try {
      if (process.env.NODE_ENV === "production") {
        font = await p.loadFont("/static/assets/Roboto_Condensed-Light.ttf"); // 載入字體檔案
        boldFont = await p.loadFont(
          "/static/assets/Roboto_Condensed-Medium.ttf"
        );
        barcodeFont = await p.loadFont(
          "/static/assets/LibreBarcode39Text-Regular.ttf"
        );
        zh_font = await p.loadFont("/static/assets/Dotted Songti Circle.otf");
        zh_boldFont = await p.loadFont("/static/assets/NotoSansTC-Bold.ttf");
      } else {
        font = await p.loadFont("assets/Roboto_Condensed-Light.ttf"); // 載入字體檔案
        boldFont = await p.loadFont("assets/Roboto_Condensed-Medium.ttf");
        barcodeFont = await p.loadFont("assets/LibreBarcode39Text-Regular.ttf");
        zh_font = await p.loadFont("assets/Dotted Songti Circle.otf");
        zh_boldFont = await p.loadFont("assets/NotoSansTC-Bold.ttf");
      }
      p.textFont(font); // 設定字體
      logFont = font;
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
      addScrollEntry(
        `[${timestamp}] > RECEIVE..|..ENDPOINT(127.0.0.1:61373) OPCODE(DMX) SEQUENCE(0) PHYSICAL(0) UNIVERSE(0) DATA(${data.value.toString()})\n`
      );
    });
    socket.on("tsoo_param", (data) => {
      previousTsooParam = tsooParam;
      tsooParam = data;
      if (
        tsooParam.area_people_count === undefined ||
        previousTsooParam.area_people_count === undefined
      )
        return;
      if (
        tsooParam.area_people_count.toString() !==
        previousTsooParam.area_people_count.toString()
      ) {
        peopleRandomPos = [];
        for (let i = 0; i < tsooParam.area_people_count.length; i++) {
          let pos = [];
          for (let j = 0; j < tsooParam.area_people_count[i]; j++) {
            pos.push({
              x: p.random(-30, 30),
              y: p.random(-30, 30),
              z: 0,
            });
          }
          peopleRandomPos.push(pos);
        }
        console.log(peopleRandomPos);
      }
    });

    // p.camera(400, -400, 500);
    // capture = p.createCapture(p.VIDEO);
    // capture.hide();
    setInterval(() => {
      const timestamp = new Date().toISOString(); // 生成 ISO 格式的時間碼
      addScrollEntry(
        `[${timestamp}] > RECEIVE..|..NDPOINT(127.0.0.1:6454) OPCODE(POLL)\n`
      );
    }, 3000);

    if ("geolocation" in navigator) {
      /* geolocation is available */
      console.log("geolocation available");
      navigator.geolocation.getCurrentPosition((position) => {
        console.log(position.coords.latitude, position.coords.longitude);
        location = position.coords;
      });
    } else {
      /* geolocation IS NOT available */
      console.log("geolocation IS NOT available");
    }
  };
  function buildLogSegments(line) {
    const cleanedLine = line.replace(/\n$/, "");
    const segments = [];
    p.push();
    p.textFont(logFont || font);
    p.textSize(LOG_TEXT_SIZE);
    const parts = cleanedLine.split(LOG_TOKEN_REGEX);
    for (const part of parts) {
      if (!part) continue;
      const color = LOG_TOKEN_COLORS[part] || LOG_TOKEN_COLORS.DEFAULT;
      segments.push({
        text: part,
        fill: color,
        width: p.textWidth(part),
      });
    }
    p.pop();
    return segments;
  }

  function addScrollEntry(line) {
    scroll_dmx_data[logWriteIndex] = buildLogSegments(line);
    logWriteIndex = (logWriteIndex + 1) % max_lines;
    if (logCount < max_lines) {
      logCount++;
    }
  }

  p.draw = () => {
    p.background("#000000ff");
    p.textAlign(p.LEFT, p.TOP);
    p.textSize(3);
    p.orbitControl();
    // p.image(capture, -p.width / 2, -p.height / 3, 400, 225);
    let orthoScale = 8;
    p.ortho(
      -p.width / orthoScale,
      p.width / orthoScale,
      -p.height / orthoScale,
      p.height / orthoScale,
      0,
      1000
    );
    // p.push();
    // p.fill(255);
    // p.textSize(8);
    // p.textFont(barcodeFont);
    // p.text(
    //   "*Tender Soul of Ocean*\n*How could I survive*\n*The answer lies within*",
    //   153,
    //   70
    // );
    // p.pop();
    p.fill(255);
    p.ellipse(0, 0, 250, 250, 50);
    p.push();
    p.translate(-200, 30);
    let ws = tsooParam.wind_speed;
    let wd = tsooParam.wind_angle;
    if (wd === undefined) {
      ws = 0;
      wd = 0;
    }
    p.fill(0);
    p.textAlign(p.RIGHT, p.BOTTOM);
    p.textSize(3.2);
    p.textFont(zh_font);
    p.text(`#現在風速_wind_speed -> ${ws} m/s`, 150 * 1.5, -60 * 1.5);
    p.text(`#現在風向_wind_direction -> ${wd} °`, 149.7 * 1.5, -63 * 1.5);

    p.stroke(0);
    p.strokeWeight(0.08);
    p.line(151 * 1.5, -60.5 * 1.5, 182 * 1.5, -56 * 1.5);

    p.translate(200 * 1.4, -50 * 1.4, 0);
    p.text(convertWindAngleToDirection(wd), -25, -12);
    p.noFill();
    p.stroke(0);
    p.strokeWeight(0.1);
    p.circle(0, 0, 32);
    p.rotateX(p.PI);
    p.rotateZ(p.radians(wd));
    p.cylinder(0.75, 24, 4);
    p.translate(0, 12, 0);
    p.cone(2.5, 5, 4);

    p.pop();
    // for (let i = 0; i < 4; i++) {
    //   drawAreaPeople(
    //     p,
    //     i,
    //     peopleRandomPos,
    //     targetAreaCircleSize,
    //     currentAreaCircleSize
    //   );
    // }

    p.push();
    p.textSize(5);
    p.textFont(zh_font);
    p.fill(0, 200);
    p.textAlign(p.CENTER);
    let lat = p.round(p.random(-5, 5));
    let long = p.round(p.random(-5, 5));
    p.text(
      `台中, 勤美 [${
        (p.round(location.latitude * 10000000) + lat) / 10000000
      } ${(p.round(location.longitude * 10000000) + long) / 10000000}]`,
      -66,
      -30
    );
    p.textSize(24);
    p.textFont(boldFont);
    p.fill(0);
    // p.text("Tender Soul of Ocean : recall", -205, -10);
    p.textSize(13 / 2);
    p.fill(0);
    // p.rect(235, 0, 200, 20);
    p.fill(0);
    // p.text("WHYIXD x KLING KLANG KLONG", 280, 0);
    p.pop();

    // 繪製 DMX 資料，最新資料在最下方
    p.push();
    p.textFont(logFont || font);
    p.textSize(LOG_TEXT_SIZE);
    p.translate(160, 77);

    let y = -p.height / 6 + 80;
    for (let i = 0; i < logCount; i++) {
      const bufferIndex =
        (logWriteIndex - logCount + i + max_lines) % max_lines;
      const entry = scroll_dmx_data[bufferIndex];
      if (!entry) continue;
      let x = -p.width / 6 + 50;
      for (const segment of entry) {
        p.fill(...segment.fill);
        p.text(segment.text, x, y);
        x += segment.width;
      }

      y += 2.1; // 每行文字的間距
    }
    p.fill(255, 30);
    p.textSize(10);
    p.textFont(boldFont);
    // p.text("TSOO", -295, 124);
    p.pop();
    p.rotateX(p.PI / 2);
    p.rotateZ(-p.PI / 2);

    // p.push();
    // p.rotateY(p.PI / 2);
    // p.strokeWeight(0.1);
    // p.noFill();
    // p.stroke(255);
    // p.rect(-70*1.5, -150*1.5, 140*1.5, 300*1.5);
    // p.pop();

    // p.push();
    // p.noStroke();
    // p.strokeWeight(0.1);
    // p.fill(255, 196, 0);
    // // 讓球體更靠近camera
    // p.rotateY(-p.PI / 4);
    // p.rotateX(p.PI / 2);
    // p.translate(-500, 500, 0);
    // p.rotateY(p.frameCount * 0.001);

    // p.scale(1.9); // <--- 這裡調整整體大小

    // let boxSize = 20;
    // for (let i = 0; i < startPosition.length; i++) {
    //   p.translate(
    //     startPosition[i].x * 1.5,
    //     startPosition[i].y * 1.5,
    //     startPosition[i].z
    //   );
    //   if (dmx_data[i * 16] !== undefined)
    //     // p.box((dmx_data[i * 16] / 255) * boxSize);
    //     for (let j = 1; j < 16; j++) {
    //       // 使用 sinParams[i]
    //       let a = [
    //         0,
    //         p.sin(j * sinParams[i].sinLength + sinParams[i].sinOffset) *
    //           sinParams[i].sinScale +
    //           sinParams[i].sinYOffset +
    //           p.random(0.05),
    //         11.12,
    //       ];
    //       //11.12
    //       p.translate(a[0], a[1], a[2]);
    //       // p.box(0.2);
    //       let dmxValue =
    //         dmx_data[i * 16 + j] === undefined ? 0 : dmx_data[i * 16 + j];
    //       // p.box((dmxValue / 255) * boxSize);
    //       if (dmxValue > 10) {
    //         p.stroke(255);
    //         p.strokeWeight(0.01);
    //         p.line(0, 0, 0, 0, 10000, 0);
    //       }
    //     }
    // }
    // p.pop();
  };

  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
};

new p5(sketch);
