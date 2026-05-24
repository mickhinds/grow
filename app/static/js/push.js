/* Grow — Web Push subscription manager */

(function() {
  'use strict';

  // VAPID public key is injected by the template
  var vapidKey = document.querySelector('meta[name="vapid-key"]');
  if (!vapidKey) return;
  var applicationServerKey = vapidKey.content;
  if (!applicationServerKey) return;

  // Check browser support
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.log('Push notifications not supported in this browser.');
    return;
  }

  // URL-safe base64 to Uint8Array
  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; i++) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  // Register service worker and subscribe
  navigator.serviceWorker.register('/static/sw.js')
    .then(function(registration) {
      console.log('Service worker registered.');
      return registration.pushManager.getSubscription()
        .then(function(subscription) {
          if (subscription) {
            // Already subscribed — send to server in case it's a new device/reinstall
            return sendSubscriptionToServer(subscription);
          }
          // Subscribe
          return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(applicationServerKey)
          }).then(function(subscription) {
            return sendSubscriptionToServer(subscription);
          });
        });
    })
    .catch(function(err) {
      console.log('Push subscription failed:', err);
    });


  function sendSubscriptionToServer(subscription) {
    var key = subscription.getKey('p256dh');
    var auth = subscription.getKey('auth');

    // Get CSRF token from meta tag
    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfMeta ? csrfMeta.content : '';

    return fetch('/push/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        p256dh: btoa(String.fromCharCode.apply(null, new Uint8Array(key))),
        auth: btoa(String.fromCharCode.apply(null, new Uint8Array(auth)))
      })
    }).then(function(response) {
      if (response.ok) {
        console.log('Push subscription saved.');
      }
    });
  }
})();
