const loc = window.location;
const wsProtocol = loc.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = wsProtocol + "//" + loc.host + "/ws";

const ws = new WebSocket(wsUrl);
const img = document.getElementById("stream");

ws.binaryType = "arraybuffer";

ws.onmessage = (event) => {
    const blob = new Blob([event.data], { type: "image/jpeg" });
    img.src = URL.createObjectURL(blob);
};

ws.onopen = () => console.log("Connected to stream at", wsUrl);
ws.onclose = () => console.log("Disconnected");