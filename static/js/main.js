console.log("Main JS loaded");

let selectedVibe = "";

// Scroll to final input section
function scrollToVibe() {
    document.querySelector(".final-input-section")
        .scrollIntoView({ behavior: "smooth" });
}

// Step 1: After user types vibe
function handleVibeStep() {

    const vibeInput = document.getElementById("finalVibeInput").value.trim();

    if (!vibeInput) {
        alert("Please tell us how you feel.");
        return;
    }

    selectedVibe = vibeInput;

    document.getElementById("locationStep")
        .classList.remove("hidden");
}

// Show manual location box
function showManualLocation() {
    document.getElementById("manualLocationBox")
        .classList.remove("hidden");
}

// Manual location submit
function submitManualLocation() {

    const location = document.getElementById("manualLocationInput")
        .value.trim();

    if (!location) {
        alert("Please enter a location.");
        return;
    }

    const payload = {
        vibe: selectedVibe,
        location: location,
        age: "",
        personality: "",
        useCoords: false
    };

    sessionStorage.setItem("vibeData",
        JSON.stringify(payload));

    window.location.href = "/results";
}

// Current location
function useCurrentLocation() {

    if (!navigator.geolocation) {
        alert("Geolocation not supported.");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        function(position) {

            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            const payload = {
                vibe: selectedVibe,
                location: `${lat},${lng}`,
                age: "",
                personality: "",
                useCoords: true
            };

            sessionStorage.setItem("vibeData",
                JSON.stringify(payload));

            window.location.href = "/results";
        },
        function(error) {
            alert("Location permission denied.");
        }
    );
}