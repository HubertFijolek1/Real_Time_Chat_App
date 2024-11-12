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

        try {
            let response = await fetch('/token', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                console.error(`Login failed with status ${response.status}`);
                // If login failed, attempt to register
                response = await fetch('/users/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: username, password: enteredPassword})
                });

                if (response.ok) {
                    console.log("Registration successful, attempting to log in");
                    // Registration successful, now login
                    response = await fetch('/token', {
                        method: 'POST',
                        body: formData
                    });
                } else {
                    const errorData = await response.json();
                    console.error("Registration failed:", errorData);
                    alert(`Failed to register: ${JSON.stringify(errorData.detail)}`);
                    return;
                }
            }

            if (response.ok) {
                const data = await response.json();
                token = data.access_token;
                console.log("Token obtained:", token);

                // Join the chat room
                try {
                    console.log("Attempting to join chat room...");
                    const joinResponse = await fetch(`/chat_rooms/${currentChatRoomId}/join`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            // Do not set 'Content-Type' header for requests without a body
                        },
                    });
                    if (!joinResponse.ok) {
                        const errorData = await joinResponse.json();
                        console.error("Join chat room failed:", errorData);
                        alert(`Failed to join chat room: ${JSON.stringify(errorData.detail)}`);
                        return;
                    }
                    console.log("Joined chat room successfully.");

                    usernameContainer.style.display = "none";
                    messages.style.display = "block";
                    inputContainer.style.display = "flex";

                    // Now connect to WebSocket
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${protocol}//${window.location.host}/ws/${currentChatRoomId}?token=${token}`;
                    console.log(`Connecting to WebSocket at ${wsUrl}`);
                    ws = new WebSocket(wsUrl);

                    ws.onopen = function() {
                        console.log("WebSocket connection opened.");
                    };

                    ws.onmessage = function(event) {
                        console.log("WebSocket message received:", event.data);
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

                    ws.onerror = function(event) {
                        console.error("WebSocket error observed:", event);
                    };

                    ws.onclose = function(event) {
                        console.log("WebSocket is closed now.", event);
                    };

                    sendButton.onclick = function() {
                        const message = input.value;
                        if (message) {
                            console.log("Sending message:", message);
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
                            console.log("Sending typing indicator");
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
                        console.log("Uploading file:", file.name);
                        const response = await fetch("/upload/", {
                            method: "POST",
                            headers: {
                                "Authorization": `Bearer ${token}`
                                // Do not set 'Content-Type' header when sending FormData
                            },
                            body: formData
                        });
                        const data = await response.json();
                        if (!response.ok) {
                            console.error("File upload failed:", data);
                            alert(`File upload failed: ${data.detail}`);
                            return;
                        }
                        console.log("File uploaded successfully:", data.file_url);
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

                } catch (error) {
                    console.error("Error during joining chat room:", error);
                    alert(`Error joining chat room: ${error.message}`);
                    return;
                }
            } else {
                const errorData = await response.json();
                console.error("Login failed:", errorData);
                alert(`Failed to login: ${JSON.stringify(errorData.detail)}`);
            }
        } catch (error) {
            console.error("Error during login/register process:", error);
            alert(`Error: ${error.message}`);
        }
    }
};

let typingTimeout;
