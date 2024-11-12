let token = "";
let currentChatRoomId = 1; // For simplicity, assume chat room ID is 1.

const messages = document.getElementById("messages");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const usernameInput = document.getElementById("username-input");
const passwordInput = document.getElementById("password-input");
const usernameButton = document.getElementById("username-button");
const usernameContainer = document.getElementById("username-container");
const inputContainer = document.getElementById("input-container");
const fileInput = document.getElementById("file-input");
const emojiPicker = document.getElementById("emoji-picker");
const typingIndicator = document.getElementById("typing-indicator");

let username = "";
let ws;

usernameButton.onclick = async function() {
    const enteredUsername = usernameInput.value.trim();
    const enteredPassword = passwordInput.value.trim();
    if (enteredUsername && enteredPassword) {
        username = enteredUsername;
        // Attempt to login
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', enteredPassword);

        let response = await fetch('/token', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            // If login failed, attempt to register
            response = await fetch('/users/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: username, password: enteredPassword})
            });

            if (response.ok) {
                // Registration successful, now login
                response = await fetch('/token', {
                    method: 'POST',
                    body: formData
                });
            }
        }

        if (response.ok) {
            const data = await response.json();
            token = data.access_token;

            usernameContainer.style.display = "none";
            messages.style.display = "block";
            inputContainer.style.display = "flex";

            // Now connect to WebSocket
            const wsUrl = `ws://${window.location.host}/ws/${currentChatRoomId}?token=${token}`;
            ws = new WebSocket(wsUrl);

            ws.onopen = function() {
                ws.send(JSON.stringify({type: "join", content: `${username} has joined the chat.`}));
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === "chat") {
                    const msg = document.createElement("div");
                    msg.classList.add("message");
                    if (data.is_attachment) {
                        const text = document.createElement("span");
                        text.textContent = `${data.username} sent a file: `;
                        const link = document.createElement("a");
                        link.href = data.content;
                        link.textContent = "Download file";
                        link.target = "_blank";
                        msg.appendChild(text);
                        msg.appendChild(link);
                    } else {
                        msg.textContent = `${data.username}: ${data.content}`;
                    }
                    msg.dataset.messageId = data.message_id;
                    // Add reactions display
                    const reactionsDiv = document.createElement("div");
                    reactionsDiv.classList.add("reactions");
                    msg.appendChild(reactionsDiv);

                    // Add reaction buttons
                    const reactionButtons = ['😊', '👍', '❤️'].map(emoji => {
                        const button = document.createElement("button");
                        button.classList.add("reaction-button");
                        button.textContent = emoji;
                        button.onclick = () => {
                            ws.send(JSON.stringify({
                                type: "reaction",
                                message_id: data.message_id,
                                reaction_type: emoji,
                                chat_room_id: currentChatRoomId
                            }));
                        };
                        return button;
                    });
                    reactionButtons.forEach(button => reactionsDiv.appendChild(button));

                    messages.appendChild(msg);
                    messages.scrollTop = messages.scrollHeight;
                } else if (data.type === "typing") {
                    typingIndicator.textContent = `${data.username} is typing...`;
                    clearTimeout(typingTimeout);
                    typingTimeout = setTimeout(() => {
                        typingIndicator.textContent = "";
                    }, 3000);
                } else if (data.type === "reaction") {
                    // Update message with new reaction
                    const messageElements = messages.getElementsByClassName("message");
                    for (let msgElement of messageElements) {
                        if (msgElement.dataset.messageId == data.message_id) {
                            const reactionsDiv = msgElement.querySelector(".reactions");
                            const reactionSpan = document.createElement("span");
                            reactionSpan.textContent = `${data.username} reacted with ${data.reaction_type}`;
                            reactionsDiv.appendChild(reactionSpan);
                            break;
                        }
                    }
                }
                // Handle other message types
            };

            sendButton.onclick = function() {
                const message = input.value;
                if (message) {
                    ws.send(JSON.stringify({
                        type: "chat",
                        content: message,
                        is_attachment: false,
                        chat_room_id: currentChatRoomId
                    }));
                    input.value = "";
                }
            };

            input.addEventListener("keypress", function(event) {
                if (event.key === "Enter") {
                    sendButton.click();
                } else {
                    ws.send(JSON.stringify({
                        type: "typing",
                        chat_room_id: currentChatRoomId
                    }));
                }
            });

            fileInput.onchange = async function() {
                const file = fileInput.files[0];
                const formData = new FormData();
                formData.append("file", file);
                const response = await fetch("/upload/", {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`
                    },
                    body: formData
                });
                const data = await response.json();
                ws.send(JSON.stringify({
                    type: "chat",
                    content: data.file_url,
                    is_attachment: true,
                    chat_room_id: currentChatRoomId
                }));
            };

            // Emoji picker handling
            emojiPicker.addEventListener('emoji-click', event => {
                input.value += event.detail.unicode;
            });
        } else {
            alert("Failed to login or register.");
        }
    }
};

let typingTimeout;