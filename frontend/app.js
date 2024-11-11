const ws = new WebSocket("ws://localhost:8000/ws");

const messages = document.getElementById("messages");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const usernameInput = document.getElementById("username-input");
const usernameButton = document.getElementById("username-button");
const usernameContainer = document.getElementById("username-container");
const inputContainer = document.getElementById("input-container");
const typingIndicator = document.getElementById("typing-indicator");
let typingTimeout;

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
input.addEventListener("keypress", function(event) {
    if (event.key !== "Enter") {
        ws.send(JSON.stringify({
            type: "typing",
            chat_room_id: currentChatRoomId
        }));
    }
});

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === "typing") {
        typingIndicator.textContent = `${data.username} is typing...`;
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
            typingIndicator.textContent = "";
        }, 3000);
    } else {
        const msg = document.createElement("div");
    msg.classList.add("message");
    msg.textContent = event.data;
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
    }
};