function findVibe() {
    const vibe = document.getElementById("vibeInput").value;
    const location = document.getElementById("locationInput").value;
    const age = document.getElementById("ageInput").value;
    const personality = document.getElementById("personalityInput").value;

    if (!vibe || !location) {
        alert("Please enter vibe and location");
        return;
    }

    const payload = {
        vibe: vibe,
        location: location,
        age: age,
        personality: personality
    };

    // Save input temporarily (no database)
    sessionStorage.setItem("vibeData", JSON.stringify(payload));

    // Go to results page
    window.location.href = "/results";
}
function useCurrentLocation() {
    navigator.geolocation.getCurrentPosition(position => {
        const data = JSON.parse(sessionStorage.getItem("vibeData"));
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        data.location = `${lat},${lng}`;
        data.coords = { lat: lat, lng: lng };
        data.useCoords = true;
        sessionStorage.setItem("vibeData", JSON.stringify(data));
        window.location.href = "/results";
    });
}
function submitManualLocation() {
    const manual = document.getElementById("manualLocationInput").value;

    if (!manual) {
        alert("Enter location");
        return;
    }

    const data = JSON.parse(sessionStorage.getItem("vibeData"));
    data.location = manual;
    sessionStorage.setItem("vibeData", JSON.stringify(data));

    window.location.href = "/results";
}