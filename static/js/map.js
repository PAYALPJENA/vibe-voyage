let map;
let markers = [];
let wishlistSet = new Set();

window.onload = function () {
    const data = sessionStorage.getItem("vibeData");

    if (!data) {
        alert("No vibe data found — please enter your vibe.");
        // redirect back to vibe input
        window.location.href = '/vibe';
        return;
    }

    const vibeData = JSON.parse(data);
    setupPersonalization(vibeData);

    // load existing wishlist to prevent duplicates, then fetch recommendations
    fetch('/api/wishlist').then(r => r.json()).then(j => {
        if (j && j.wishlist) {
            j.wishlist.forEach(i => wishlistSet.add(i.place_name));
        }
        fetchRecommendations(vibeData);
    }).catch(() => fetchRecommendations(vibeData));
};

function setupPersonalization(vibeData) {
    // Placeholder for future personalization controls
}

function fetchRecommendations(vibeData) {
    const payload = Object.assign({}, vibeData);
    
    fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json().then(body => ({ ok: res.ok, status: res.status, body })))
    .then(({ ok, status, body }) => {
        const messageEl = document.getElementById('results_message');
        if (!ok) {
            const msg = body && body.error ? body.error : 'Failed to interpret request';
            if (messageEl) messageEl.innerText = msg + ' — try refining your vibe.';
            else console.warn(msg);
            const container = document.getElementById('places');
            if (container) container.innerHTML = `<p style="color:#d9534f">${msg}. <a href="/vibe">Refine your vibe</a></p>`;
            return;
        }

        const places = body;
        if (!places || places.length === 0) {
            const container = document.getElementById('places');
            if (container) container.innerHTML = '<p>No places found for this vibe. <a href="/vibe">Try again</a></p>';
            return;
        }

        // Ensure map container has height so Google Maps can render
        const mapEl = document.getElementById('map');
        if (mapEl && mapEl.offsetHeight === 0) {
            mapEl.style.minHeight = '480px';
        }

        initMap(places);
        showPlaces(places, vibeData);
    })
    .catch(err => {
        console.error(err);
        const container = document.getElementById('places');
        if (container) container.innerHTML = '<p>Failed to load recommendations. <a href="/vibe">Try again</a></p>';
    });
}

function initMap(places) {
    const center = {
        lat: places[0].latitude,
        lng: places[0].longitude
    };

    if (!map) {
        map = new google.maps.Map(document.getElementById("map"), {
            zoom: 13,
            center: center
        });
    } else {
        map.panTo(center);
        map.setZoom(13);
    }

    // Clear old markers
    markers.forEach(m => m.setMap(null));
    markers = [];

    places.forEach(place => {
        const marker = new google.maps.Marker({
            position: { lat: place.latitude, lng: place.longitude },
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

function showPlaces(places, vibeData) {
    const container = document.getElementById("places");
    container.innerHTML = "";

    places.forEach((place, idx) => {
        const card = document.createElement("div");
        card.className = "place-card";

        const imageHTML = place.photo_ref
            ? `<img 
                src="https://maps.googleapis.com/maps/api/place/photo?maxwidth=300&photo_reference=${place.photo_ref}&key=AIzaSyCB8ugDH0XlhxJaud08gZepoYpkfvucTBI"
                class="place-img-thumb"
                onclick="openImageModal(this.src.replace('maxwidth=300','maxwidth=1200'))"
              />`
            : `<div class="no-img">No Image</div>`;

        let feedbackHTML = "";
        if (place.feedback_count > 0) {
            feedbackHTML = `<p class="feedback-stats">👥 ${place.feedback_count} rating(s) • ⭐ ${place.feedback_avg_rating}/5</p>`;
        }

        card.innerHTML = `
            ${imageHTML}
            <h4>${place.name}</h4>
            <p class="desc">${place.description}</p>
            <p>⭐ ${place.rating} (${place.reviews || 0} reviews)</p>
            <span>Best time: ${place.best_time}</span>
            ${feedbackHTML}
            <br>
            <button class="btn-feedback">⭐ Rate This Place</button>
            <button class="btn-wishlist" data-name="${place.name}">+ Wishlist</button>
            <br>
            <span style="cursor:pointer;color:#38bdf8;margin-top:8px;display:block;" onclick="openInGoogleMaps(${place.latitude}, ${place.longitude})">Open in Google Maps</span>
        `;

        // Clicking card zooms map
        card.addEventListener("click", (e) => {
            if (e.target.tagName === "IMG" || e.target.className === "btn-feedback") return;
            map.panTo({ lat: place.latitude, lng: place.longitude });
            map.setZoom(15);
        });

        container.appendChild(card);

        // Feedback/Rating button handler
        const feedbackBtn = card.querySelector('.btn-feedback');
        if (feedbackBtn) {
            feedbackBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openFeedbackModal(place.name, vibeData.location || 'Unknown');
            });
        }

        // Wishlist button handler
        const wishBtn = card.querySelector('.btn-wishlist');
        if (wishBtn) {
            // disable if already in wishlist
            if (wishlistSet.has(place.name)) {
                wishBtn.textContent = 'Saved';
                wishBtn.disabled = true;
            }

            wishBtn.addEventListener('click', (e) => {
                const btn = e.currentTarget;
                if (wishlistSet.has(place.name)) return; // double-check
                btn.disabled = true;
                btn.textContent = 'Saving...';

                const payload = {
                    place_name: place.name,
                    place_data: {
                        name: place.name,
                        description: place.description,
                        rating: place.rating,
                        reviews: place.reviews,
                        latitude: place.latitude,
                        longitude: place.longitude,
                        category: place.category,
                        photo_ref: place.photo_ref || null
                    }
                };

                fetch('/api/wishlist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                })
                .then(res => res.json())
                .then(j => {
                    if (j && j.success) {
                        wishlistSet.add(place.name);
                        btn.textContent = 'Saved';
                        showToast('Added to wishlist');
                    } else {
                        btn.textContent = '+ Wishlist';
                        btn.disabled = false;
                        showToast(j && j.error ? j.error : 'Failed to add to wishlist', true);
                    }
                })
                .catch(err => {
                    console.error(err);
                    btn.textContent = '+ Wishlist';
                    btn.disabled = false;
                    showToast('Failed to add to wishlist', true);
                });
            });
        }

        // Attach infoWindow wishlist button to corresponding marker
        const marker = markers[idx];
        if (marker) {
            const safeId = ('wishlist_btn_' + place.name).replace(/[^a-zA-Z0-9_]/g, '_');
            const infoContent = `<div style="max-width:220px;"><h4>${place.name}</h4><p style='font-size:0.9rem'>${place.description || ''}</p><button id="${safeId}">${wishlistSet.has(place.name)?'Saved':'+ Wishlist'}</button></div>`;
            const infoWindow = new google.maps.InfoWindow({ content: infoContent });

            marker.addListener('click', () => {
                infoWindow.open(map, marker);
                google.maps.event.addListenerOnce(infoWindow, 'domready', () => {
                    const btn = document.getElementById(safeId);
                    if (!btn) return;
                    if (wishlistSet.has(place.name)) { btn.disabled = true; }
                    btn.addEventListener('click', () => {
                        if (wishlistSet.has(place.name)) return;
                        btn.textContent = 'Saving...';
                        fetch('/api/wishlist', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ place_name: place.name, place_data: { name: place.name, description: place.description, rating: place.rating, reviews: place.reviews, latitude: place.latitude, longitude: place.longitude, category: place.category } })
                        }).then(r=>r.json()).then(j=>{
                            if (j && j.success) {
                                wishlistSet.add(place.name);
                                btn.textContent = 'Saved';
                                btn.disabled = true;
                                showToast('Added to wishlist');
                            } else {
                                btn.textContent = '+ Wishlist';
                                showToast(j && j.error ? j.error : 'Failed to add', true);
                            }
                        }).catch(e=>{ console.error(e); btn.textContent = '+ Wishlist'; showToast('Failed to add', true); });
                    });
                });
            });
        }

    });
}

// FULLSCREEN IMAGE MODAL
function openImageModal(src) {
    const modal = document.createElement("div");
    modal.className = "image-modal";

    modal.innerHTML = `
        <div class="image-modal-content">
            <img src="${src}" />
        </div>
    `;

    document.body.style.overflow = "hidden";

    modal.onclick = () => {
        document.body.style.overflow = "auto";
        modal.remove();
    };

    document.body.appendChild(modal);
}


function openInGoogleMaps(lat, lng) {
    const url = `https://www.google.com/maps?q=${lat},${lng}`;
    window.open(url, "_blank");
}

// Simple toast notification
function showToast(msg, isError=false) {
    let t = document.getElementById('app_toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'app_toast';
        t.style.position = 'fixed';
        t.style.right = '20px';
        t.style.bottom = '20px';
        t.style.zIndex = 10000;
        document.body.appendChild(t);
    }
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.background = isError ? 'rgba(220,53,69,0.95)' : 'rgba(56,189,248,0.95)';
    el.style.color = '#fff';
    el.style.padding = '10px 14px';
    el.style.marginTop = '8px';
    el.style.borderRadius = '8px';
    el.style.boxShadow = '0 6px 18px rgba(0,0,0,0.15)';
    el.style.fontSize = '0.95rem';
    t.appendChild(el);
    setTimeout(() => { el.style.transition = 'opacity 0.25s'; el.style.opacity = '0'; setTimeout(()=>el.remove(),300); }, 3000);
}
