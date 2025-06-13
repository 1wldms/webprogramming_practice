document.addEventListener('mousemove', e => {
    const xPct = (e.clientX / window.innerWidth)  * 100;
    const yPct = (e.clientY / window.innerHeight) * 100;
    document.documentElement.style.setProperty('--x', `${xPct}%`);
    document.documentElement.style.setProperty('--y', `${yPct}%`);
});
    document.getElementById("feedback-btn").onclick = function () {
    document.getElementById("feedback-modal").classList.remove("hidden");
};

function closeFeedback() {
    document.getElementById("feedback-modal").classList.add("hidden");
}

    document.getElementById("feedback-form").onsubmit = async function (e) {
    e.preventDefault();
    const formData = new FormData(e.target);

    const res = await fetch("/submit-feedback", {
        method: "POST",
        body: formData
    });

    const text = await res.text();
    alert(text);
    closeFeedback();
};