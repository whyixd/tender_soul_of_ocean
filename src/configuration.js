import p5, { add, update } from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";

if (process.env.NODE_ENV === "production") {
  p5.disableFriendlyErrors = true;
}

const sketch = (p) => {
  const boxDepth = 25; // Z-axis
  const boxWidth = boxDepth * 2; // X-axis
  const boxHeight = boxDepth * 2; // Y-axis

  const gridConfig = {
    cellSize: 25,
    cellsX: 6,
    cellsZ: 6,
    get sizeX() {
      return this.cellsX * this.cellSize;
    },
    get sizeZ() {
      return this.cellsZ * this.cellSize;
    },
    saveUnitConfig: () => {
      console.log("Saving unit configuration to backend...");
      updateUnitConfig2Config();
    },
  };

  const boxes = [
    {
      id: 0,
      name: "Unit 1",
      x: 0,
      y: -boxHeight / 2,
      z: 0,
      cordX: 0,
      cordZ: 0,
    }, // Z will be corrected in setup
  ];
  let nextBoxId = 1;
  let selectedBox = boxes[0];

  let previewPosition = { x: 0, z: 0 };
  let isDragging = false;

  let font;

  let unitConfig;

  // --- New Snapping Logic ---
  const snapToGridX = (value) => {
    // Snap to the nearest grid line (for even multiples)
    return Math.round(value / gridConfig.cellSize) * gridConfig.cellSize;
  };
  const snapToGridZ = (value) => {
    // Snap to the center of the nearest grid cell (for odd multiples)
    return (
      Math.floor(value / gridConfig.cellSize) * gridConfig.cellSize +
      gridConfig.cellSize / 2
    );
  };
  const calculateCoordinatesX = (value) => {
    return (value + gridConfig.sizeX / 2) / gridConfig.cellSize - 1;
  };
  const calculateCoordinatesZ = (value) => {
    return (value + gridConfig.sizeZ / 2) / gridConfig.cellSize - 0.5;
  };
  let boxGui, controllerX, controllerZ, boxSelector;

  const hasCollisionAt = (x, z, ignoredId = -1) => {
    return boxes.some(
      (box) =>
        box.id !== ignoredId &&
        Math.abs(x - box.x) < boxWidth &&
        Math.abs(z - box.z) < boxDepth
    );
  };
  function addBox() {
    let newX = 0;
    let newZ = snapToGridZ(0); // Start at a valid snapped Z position
    while (hasCollisionAt(newX, newZ)) {
      newX += gridConfig.cellSize;
    }
    const newName = `Unit ${nextBoxId + 1}`;
    const newBox = {
      id: nextBoxId,
      name: newName,
      x: newX,
      y: -boxHeight / 2,
      z: newZ,
    };
    boxes.push(newBox);
    nextBoxId++;
    guiState.selectedBoxName = newName;
    refreshBoxSelector();
    selectedBox.cordX = calculateCoordinatesX(selectedBox.x);
    selectedBox.cordZ = calculateCoordinatesZ(selectedBox.z);
  }
  const guiState = {
    get selectedBoxName() {
      return selectedBox ? selectedBox.name : "";
    },
    set selectedBoxName(name) {
      const box = boxes.find((b) => b.name === name);
      if (box) {
        selectedBox = box;
        previewPosition.x = selectedBox.x;
        previewPosition.z = selectedBox.z;
        if (controllerX) controllerX.updateDisplay();
        if (controllerZ) controllerZ.updateDisplay();
      }
    },
    addBox: () => {
      addBox();
      // let newX = 0;
      // let newZ = snapToGridZ(0); // Start at a valid snapped Z position
      // while (hasCollisionAt(newX, newZ)) {
      //   newX += gridConfig.cellSize;
      // }
      // const newName = `Unit ${nextBoxId + 1}`;
      // const newBox = {
      //   id: nextBoxId,
      //   name: newName,
      //   x: newX,
      //   y: -boxHeight / 2,
      //   z: newZ,
      // };
      // boxes.push(newBox);
      // nextBoxId++;
      // guiState.selectedBoxName = newName;
      // refreshBoxSelector();
      // selectedBox.cordX = calculateCoordinatesX(selectedBox.x);
      // selectedBox.cordZ = calculateCoordinatesZ(selectedBox.z);
    },
    removeBox: () => {
      if (boxes.length <= 1) {
        alert("Cannot remove the last box.");
        return;
      }
      const index = boxes.findIndex((b) => b.id === selectedBox.id);
      boxes.splice(index, 1);
      const newSelection = boxes[Math.max(0, index - 1)];
      guiState.selectedBoxName = newSelection.name;
      refreshBoxSelector();
    },
  };

  function refreshBoxSelector() {
    if (boxSelector) boxSelector.destroy();
    const boxNames = boxes.map((b) => b.name);
    boxSelector = boxGui
      .add(guiState, "selectedBoxName", boxNames)
      .name("Selected Box");
  }
  function updateUnitConfig2Config() {
    unitConfig = {
      unit_config: {
        area_size: [gridConfig.cellsX, gridConfig.cellsZ],
        units: [],
      },
    };
    unitConfig.unit_config.units = boxes.map((box) => ({
      id: box.id,
      name: box.name,
      position: {
        x: box.x,
        y: box.y,
        z: box.z,
      },
      cord: {
        x: box.cordX,
        z: box.cordZ,
      },
    }));
    const apiurl = "/api/update_unit_config";
    let result = fetch(apiurl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(unitConfig),
    })
      .then((res) => res.json())
      .then((data) => console.log(data));
  }
  function getUnitConfigFromBackend() {
    const apiurl = "/api/unit_config";
    let result = fetch(apiurl)
      .then((res) => res.json())
      .then((data) => {
        unitConfig = data;
        console.log("Fetched unit config:", unitConfig);
        gridConfig.cellsX = unitConfig.unit_config.area_size[0];
        gridConfig.cellsZ = unitConfig.unit_config.area_size[1];
        let box0 = unitConfig.unit_config.units[0];
        boxes[0].x = box0.position.x;
        boxes[0].y = box0.position.y;
        boxes[0].z = box0.position.z;
        boxes[0].cordX = box0.cord.x;
        boxes[0].cordZ = box0.cord.z;
        for (let i = 1; i < unitConfig.unit_config.units.length; i++) {
          const unit = unitConfig.unit_config.units[i];
          const newBox = {
            id: unit.id,
            name: unit.name,
            x: unit.position.x,
            y: unit.position.y,
            z: unit.position.z,
            cordX: unit.cord.x,
            cordZ: unit.cord.z,
          };
          boxes.push(newBox);
          nextBoxId = Math.max(nextBoxId, unit.id + 1);
        }
        refreshBoxSelector();
      })
      .catch((error) => {
        console.error("Error fetching unit config:", error);
      });
  }
  p.setup = async () => {
    // updateUnitConfig2Config();
    getUnitConfigFromBackend();
    // console.log("unitConfig:", unitConfig);
    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);

    // Correct initial Z position for the first box
    boxes[0].z = snapToGridZ(0);

    previewPosition.x = selectedBox.x;
    previewPosition.z = selectedBox.z;

    boxGui = new GUI();
    refreshBoxSelector();
    controllerX = boxGui.add(previewPosition, "x").name("Box X");
    controllerZ = boxGui.add(previewPosition, "z").name("Box Z");
    boxGui.add(guiState, "addBox").name("Add New Box");
    boxGui.add(guiState, "removeBox").name("Remove Selected");

    const startDragging = () => {
      isDragging = true;
    };
    controllerX.onChange(startDragging);
    controllerZ.onChange(startDragging);

    const finishDragging = () => {
      if (!isDragging) return;
      const snappedX = snapToGridX(previewPosition.x);
      const snappedZ = snapToGridZ(previewPosition.z);
      if (hasCollisionAt(snappedX, snappedZ, selectedBox.id)) {
        previewPosition.x = selectedBox.x;
        previewPosition.z = selectedBox.z;
      } else {
        selectedBox.x = snappedX;
        selectedBox.z = snappedZ;
        previewPosition.x = selectedBox.x;
        previewPosition.z = selectedBox.z;
      }
      isDragging = false;
      controllerX.updateDisplay();
      controllerZ.updateDisplay();
      selectedBox.cordX = calculateCoordinatesX(selectedBox.x);
      selectedBox.cordZ = calculateCoordinatesZ(selectedBox.z);
      console.log("Box moved to:", selectedBox.cordX, selectedBox.cordZ);
    };

    controllerX.onFinishChange(finishDragging);
    controllerZ.onFinishChange(finishDragging);

    const gridGui = new GUI();
    gridGui.domElement.style.left = "0px";
    gridGui.domElement.style.right = "auto";

    const updateBoxLimits = () => {
      const limitX = gridConfig.sizeX / 2 - boxWidth / 2;
      const limitZ = gridConfig.sizeZ / 2 - boxDepth / 2;
      controllerX.min(Math.min(-1, -limitX)).max(Math.max(1, limitX));
      controllerZ.min(Math.min(-1, -limitZ)).max(Math.max(1, limitZ));
      controllerX.updateDisplay();
      controllerZ.updateDisplay();
    };

    const controllerCellsX = gridGui
      .add(gridConfig, "cellsX", 2, 100, 2)
      .name("Grid Cells X")
      .listen();
    const controllerCellsZ = gridGui
      .add(gridConfig, "cellsZ", 2, 100, 2)
      .name("Grid Cells Z")
      .listen();
    gridGui.add(gridConfig, "saveUnitConfig").name("Save Config");
    controllerCellsX.onChange(updateBoxLimits);
    controllerCellsZ.onChange(updateBoxLimits);
    updateBoxLimits();

    try {
      if (process.env.NODE_ENV === "production") {
        font = await p.loadFont("/static/assets/Roboto_Condensed-Light.ttf");
      } else {
        font = await p.loadFont("assets/Roboto_Condensed-Light.ttf");
      }
    } catch (error) {
      console.error("Failed to load font:", error);
    }
    p.textFont(font);

    // try {
    //   if (process.env.NODE_ENV === "production") {
    //     if (fs.existsSync(path.join(__dirname, "static", "unit_setup.json"))) {
    //       unitSetup = await p.loadJSON(
    //         path.join(__dirname, "static", "unit_setup.json")
    //       );
    //     }
    //   } else {
    //     if (fs.existsSync(path.join(__dirname, "static", "unit_setup.json"))) {
    //       unitSetup = await p.loadJSON("static/unit_setup.json");
    //     }
    //   }
    // } catch (error) {
    //   console.error("Failed to load unit setup:", error);
    // }
  };

  const drawGrid = () => {
    p.push();
    p.stroke(150);
    p.strokeWeight(1);
    p.beginShape(p.LINES);
    const sizeX_half = gridConfig.sizeX / 2;
    const sizeZ_half = gridConfig.sizeZ / 2;
    for (let i = -sizeX_half; i <= sizeX_half; i += gridConfig.cellSize) {
      p.vertex(i, 0, -sizeZ_half);
      p.vertex(i, 0, sizeZ_half);
    }
    for (let i = -sizeZ_half; i <= sizeZ_half; i += gridConfig.cellSize) {
      p.vertex(-sizeX_half, 0, i);
      p.vertex(sizeX_half, 0, i);
    }
    p.endShape();
    p.pop();
  };

  const drawSnapPreview = () => {
    if (isDragging && selectedBox) {
      const snapX = snapToGridX(previewPosition.x);
      const snapZ = snapToGridZ(previewPosition.z);
      const hasCollision = hasCollisionAt(snapX, snapZ, selectedBox.id);
      p.push();
      p.translate(snapX, selectedBox.y, snapZ);
      const previewWidth = boxWidth * 1.02;
      const previewHeight = boxHeight * 1.02;
      const previewDepth = boxDepth * 1.02;
      p.push();
      p.translate(0, previewHeight / 2, 0);
      p.rotateX(p.HALF_PI);
      if (hasCollision) {
        p.fill(255, 0, 0, 70);
      } else {
        p.fill(0, 255, 0, 70);
      }
      p.noStroke();
      p.plane(previewWidth, previewDepth);
      p.pop();
      p.push();
      if (hasCollision) {
        p.stroke(255, 0, 0, 200);
      } else {
        p.stroke(0, 255, 0, 200);
      }
      p.noFill();
      p.strokeWeight(2);
      p.box(previewWidth, previewHeight, previewDepth);
      p.pop();
      p.pop();
    }
  };

  p.draw = async () => {
    p.background(200);
    if (!isDragging) {
      p.orbitControl();
    }
    drawGrid();

    boxes.forEach((box) => {
      p.push();
      p.translate(box.x, box.y, box.z);
      // Highlight the selected box ONLY when the GUI is open
      if (
        selectedBox &&
        box.id === selectedBox.id &&
        boxGui &&
        !boxGui._closed
      ) {
        p.fill(230, 230, 0); // Yellowish highlight
        p.stroke(0);
        p.strokeWeight(1.5);
      } else {
        p.fill(255); // Default white
        p.stroke(0);
        p.strokeWeight(1);
      }

      p.box(boxWidth, boxHeight, boxDepth);

      // Draw the box ID on top
      p.push();
      p.translate(0, -boxHeight / 2 - 1, 0);
      p.rotateX(p.HALF_PI);

      p.fill(0); // Black text
      p.noStroke();

      p.textAlign(p.CENTER, p.CENTER);
      p.textSize(14); // Adjust size as needed
      p.text(box.name, 0, 0);
      p.pop();

      p.pop();
    });

    drawSnapPreview();
  };

  p.doubleClicked = () => {
    p.camera();
  };
  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
};

new p5(sketch);
