document.addEventListener("DOMContentLoaded", function () {
    const registerBtn = document.querySelector(".register-btn");
    const loginBtn = document.querySelector(".login-btn");
    const container = document.querySelector(".container");

    // Check if the URL path is "/register" to show the register form
    if (window.location.pathname === "/register") {
        container.classList.add("active"); // Show register form
    } else if (window.location.pathname === "/login") {
        container.classList.remove("active"); // Show login form
    }

    registerBtn.addEventListener("click", () => {
        container.classList.add("active");
        window.history.pushState({}, "", "/register"); // Change URL
    });

    loginBtn.addEventListener("click", () => {
        container.classList.remove("active");
        window.history.pushState({}, "", "/login"); // Change URL
    });
});
