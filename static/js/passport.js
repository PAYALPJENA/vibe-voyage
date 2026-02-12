console.log("Passport JS loaded");

window.onload = function() {
    loadPassport();
};

function loadPassport() {
    fetch("/api/passport-summary")
    .then(res => res.json())
    .then(data => {

        if (data.error) {
            console.error(data.error);
            return;
        }

        renderWishlist(data.wishlist || []);
        renderTopByVibe(data.top_by_vibe || {});

    })
    .catch(err => {
        console.error("Passport load error:", err);
    });
}
function renderWishlist(items) {
    const container = document.getElementById("wishlist");
    const emptyMsg = document.getElementById("emptyWishlist");

    container.innerHTML = "";

    if (!items || items.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove("hidden");
        return;
    }

    if (emptyMsg) emptyMsg.classList.add("hidden");

    items.forEach(item => {
        const card = document.createElement("div");
        card.className = "wishlist-card";

        card.innerHTML = `
            <h3>${item.place_name}</h3>

            <div class="wishlist-meta">
                Saved under vibe: <b>${item.vibe || "Unknown"}</b>
            </div>

            <div class="wishlist-meta">
                Location: ${item.location || "Not specified"}
            </div>

            <button class="btn-feedback-cancel"
                onclick="removeFromWishlist('${item.place_name}')">
                Remove
            </button>
        `;

        container.appendChild(card);
    });
}
function renderTopByVibe(data) {
    const container = document.getElementById("vibe-summary");
    container.innerHTML = "";

    for (const vibe in data) {

        const section = document.createElement("div");
        section.className = "vibe-section-summary";

        section.innerHTML = `<h3>${vibe.toUpperCase()}</h3>`;

        const places = data[vibe];

        if (!places || places.length === 0) {
            section.innerHTML += "<p>No feedback data yet.</p>";
        } else {
            places.forEach(place => {
                section.innerHTML += `
                    <div class="place-card">
                        <h4>${place.name}</h4>
                        <p>⭐ ${place.avg_vibe_rating} (${place.vibe_count} ratings)</p>
                    </div>
                `;
            });
        }

        container.appendChild(section);
    }
}

function removeFromWishlist(placeName) {

    fetch("/api/wishlist", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ place_name: placeName })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            loadPassport(); // refresh
        }
    });
}