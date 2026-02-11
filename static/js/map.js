console.log("map.js loaded");

let map;
let markers = [];

window.onload = function () {

    const data = sessionStorage.getItem("vibeData");

    if (!data) {
        alert("No vibe data found");
        return;
    }

    const vibeData = JSON.parse(data);

    fetch("/api/recommend", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(vibeData)
    })
    .then(res => res.json())
    .then(places => {

        if (!places || places.length === 0) {
            alert("No places found");
            return;
        }

        initMap(places);
        showPlaces(places);

    })
    .catch(err => {
        console.error("API Error:", err);
        alert("Failed to load recommendations");
    });
};

function initMap(places) {

    const center = {
        lat: places[0].latitude,
        lng: places[0].longitude
    };

    map = new google.maps.Map(
        document.getElementById("map"),
        {
            zoom: 13,
            center: center,
            mapTypeId: "roadmap"
        }
    );

    markers.forEach(marker => marker.setMap(null));
    markers = [];

    places.forEach(place => {

        const marker = new google.maps.Marker({
            position: {
                lat: place.latitude,
                lng: place.longitude
            },
            map: map,
            title: place.name
        });

        marker.addListener("click", () => {
            map.panTo(marker.getPosition());
            map.setZoom(15);
        });

        markers.push(marker);
    });
}

function showPlaces(places) {

    const container = document.getElementById("places");
    container.innerHTML = "";

    places.forEach(place => {

        const card = document.createElement("div");
        card.className = "place-card";

        let imageHTML = "";

        if (place.photo_ref) {
            imageHTML = `
                <img 
                    src="https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference=${place.photo_ref}&key=AIzaSyCB8ugDH0XlhxJaud08gZepoYpkfvucTBI"
                    class="place-img-thumb"
                />
            `;
        } else {
            imageHTML = `<div class="no-img">No Image</div>`;
        }

        card.innerHTML = `
            ${imageHTML}
            <h4>${place.name}</h4>
            <p class="desc">${place.description}</p>
            <p>⭐ ${place.rating} (${place.reviews || 0} reviews)</p>
            <span>Best time: ${place.best_time}</span>
            <br>
            <span style="cursor:pointer;color:#38bdf8"
                onclick="openInGoogleMaps(${place.latitude}, ${place.longitude})">
                Open in Google Maps
            </span>
        `;

        card.addEventListener("click", (e) => {
            if (e.target.tagName === "IMG") return;

            map.panTo({
                lat: place.latitude,
                lng: place.longitude
            });

            map.setZoom(15);
        });

        container.appendChild(card);
    });
}

function openInGoogleMaps(lat, lng) {
    const url = `https://www.google.com/maps?q=${lat},${lng}`;
    window.open(url, "_blank");
}