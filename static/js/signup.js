function togglePassword() {
    const passwordInput = document.getElementById("password");
    passwordInput.type = passwordInput.type === "password" ? "text" : "password";
}

const username = document.getElementById("username");
const password = document.getElementById("password");
const genderRadios = document.querySelectorAll('input[name="gender"]');
const button = document.getElementById("submit-btn");
const form = document.getElementById("signup-form");

function checkInputs() {
    const usernameFilled = username.value.trim() !== "";
    const passwordFilled = password.value.trim() !== "";
    const genderSelected = Array.from(genderRadios).some(r => r.checked);

    if (usernameFilled && passwordFilled && genderSelected) {
    button.disabled = false;
    button.classList.add("active");
    } else {
    button.disabled = true;
    button.classList.remove("active");
    }
}

username.addEventListener("input", checkInputs);
password.addEventListener("input", checkInputs);
genderRadios.forEach(radio => radio.addEventListener("change", checkInputs));
