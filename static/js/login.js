function togglePassword() {
    const passwordInput = document.getElementById("password");
    passwordInput.type = passwordInput.type === "password" ? "text" : "password";
}

const username = document.getElementById("username");
const password = document.getElementById("password");
const button = document.getElementById("login-btn");
const form = document.getElementById("login-form");

function checkInputs() {
    const usernameFilled = username.value.trim() !== "";
    const passwordFilled = password.value.trim() !== "";

    if (usernameFilled && passwordFilled) {
        button.disabled = false;
        button.classList.add("active");
    } else {
        button.disabled = true;
        button.classList.remove("active");
    }
}

username.addEventListener("input", checkInputs);
password.addEventListener("input", checkInputs);

