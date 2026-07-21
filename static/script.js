window.addEventListener("DOMContentLoaded", () => {
  const statusValue = document.getElementById("status-value");
  const cameraStatus = document.getElementById("camera-status");

  if (statusValue && cameraStatus) {
    fetch("/health")
      .then((response) => response.json())
      .then((data) => {
        statusValue.textContent = data.status === "ok" ? "Live backend ready" : "Unavailable";
      })
      .catch(() => {
        statusValue.textContent = "Backend unavailable";
        cameraStatus.style.background = "#f87171";
        cameraStatus.style.boxShadow = "0 0 24px rgba(248, 113, 113, 0.55)";
      });
  }
});