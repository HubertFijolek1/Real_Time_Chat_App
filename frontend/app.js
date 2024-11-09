const ws = new WebSocket("ws://localhost:8000/ws");

const messages = document.getElementById("messages");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const usernameInput = document.getElementById("username-input");
const usernameButton = document.getElementById("username-button");
const usernameContainer = document.getElementById("username-container");
const inputContainer = document.getElementById("input-container");

let username = "";

usernameButton.onclick = function() {
    const enteredUsername = usernameInput.value.trim();
    if (enteredUsername) {
        username = enteredUsername;
        usernameContainer.style.display = "none";
        messages.style.display = "block";
        inputContainer.style.display = "block";
        ws.send(`${username} has joined the chat.`);
    }
};

ws.onmessage = function(event) {
    const msg = document.createElement("div");
    msg.classList.add("message");
    msg.textContent = event.data;
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
};

sendButton.onclick = function() {
    const message = input.value;
    if (message) {
        ws.send(`${username}: ${message}`);
        input.value = "";
    }
};

input.addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        sendButton.click();
    }
};