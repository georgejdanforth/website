var sha256 = null;

var intervalId = setInterval(() => {
  fetch("/sha256.txt", {cache: "no-store"})
    .then(response => {
      if (!response.ok) {
        return null;
      }
      return response.text();
    })
    .then(text => {
      if (text === null) {
        console.log("No sha256.txt found, skipping check.");
        return;
      }
      if (sha256 === null) {
        sha256 = text;
      } else if (sha256 !== text) {
        clearInterval(intervalId);
        console.log("Reloading...");
        location.reload();
      }
  });
}, 1000);
