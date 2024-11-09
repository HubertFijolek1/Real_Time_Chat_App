const ws = new WebSocket("ws://localhost:8000/ws");

const messages = document.getElementById("messages");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");

ws.onmessage = function(event) {
    const msg = document.createElement("div");
    msg.textContent = event.data;
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
};

sendButton.onclick = function() {
    const message = input.value;
    if (message) {
        ws.send(message);
        input.value = "";
    }
};