async function loadViolations() {
  try {
    const resp = await fetch("/violations");
    const data = await resp.json();

    const container = document.getElementById("violations");
    container.innerHTML = data.map(v => `
      <div class="violation" style="border:1px solid #ccc; padding:8px; margin:5px;">
        <p><b>${v.timestamp}</b></p>
        <img src="/images/${v.frame_name}" width="800"/>
        <br/>
        <button onclick="openViolation('${v.frame_id}')">Open</button>
        <button onclick="deleteViolation('${v._id}')">Delete</button>
      </div>
    `).join("");

    // add delete all button
    container.innerHTML += `
      <button style="margin-top:10px; background:red; color:white;" onclick="deleteAllViolations()">Delete All</button>
    `;
  } catch (err) {
    console.error("Failed to load violations", err);
  }
}

async function deleteViolation(id) {
  if (!confirm("Delete this violation?")) return;
  await fetch(`/violations/${id}`, { method: "DELETE" });
  loadViolations();
}

async function deleteAllViolations() {
  if (!confirm("Delete ALL violations?")) return;
  await fetch("/violations", { method: "DELETE" });
  loadViolations();
}

async function openViolation(frameId) {
  const resp = await fetch(`/violations/${frameId}`);
  const v = await resp.json();

  const img = new Image();
  img.src = `/images/${v.frame_name}`;
  img.onload = () => {
    const canvas = document.getElementById("violation-canvas");
    const ctx = canvas.getContext("2d");

    // resize canvas to match image
    canvas.width = img.width;
    canvas.height = img.height;

    ctx.drawImage(img, 0, 0);

    // draw bounding boxes (red)
    ctx.lineWidth = 2;
    ctx.strokeStyle = "red";
    v.bounding_boxes.forEach(box => {
      const [x1, y1, x2, y2] = box.bbox;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.fillStyle = "red";
      ctx.font = "16px Arial";
      ctx.fillText(box.label, x1 + 3, y1 + 15);
    });

    // draw ROIs (blue)
    ctx.strokeStyle = "blue";
    ctx.lineWidth = 2;
    v.rois.forEach(roi => {
      ctx.beginPath();
      roi.forEach(([x, y], idx) => {
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.stroke();
    });

    // show modal
    document.getElementById("violation-modal").style.display = "flex";
  };
}

function closeViolation() {
  document.getElementById("violation-modal").style.display = "none";
}


// refresh every 3s
setInterval(loadViolations, 3000);
loadViolations();
