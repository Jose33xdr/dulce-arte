/**
 * Dulce Arte - Utilidades JavaScript Base
 * Provee manejo seguro de CSRF Token y componentes interactivos básicos.
 */

// Obtener cookie CSRF de Django para peticiones fetch
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const CSRF_TOKEN = getCookie("csrftoken");

// Helper para peticiones fetch autenticadas y protegidas con CSRF
async function apiRequest(url, options = {}) {
    const defaultHeaders = {
        "X-CSRFToken": CSRF_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    };

    options.headers = { ...defaultHeaders, ...(options.headers || {}) };
    options.credentials = "same-origin";

    try {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw { status: response.status, data };
        }
        return data;
    } catch (error) {
        console.error("Error en API Request:", error);
        throw error;
    }
}

// Toggle de modales en UI
function toggleModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.toggle("hidden");
    }
}

// Manejador del menú de usuario
document.addEventListener("DOMContentLoaded", () => {
    const userMenuButton = document.getElementById("user-menu-button");
    const userMenuDropdown = document.getElementById("user-menu-dropdown");

    if (userMenuButton && userMenuDropdown) {
        userMenuButton.addEventListener("click", (e) => {
            e.stopPropagation();
            userMenuDropdown.classList.toggle("hidden");
        });

        document.addEventListener("click", () => {
            if (!userMenuDropdown.classList.contains("hidden")) {
                userMenuDropdown.classList.add("hidden");
            }
        });
    }
});
