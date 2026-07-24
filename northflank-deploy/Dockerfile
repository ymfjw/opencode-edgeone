FROM denoland/deno:alpine

# The port that your application listens to.
EXPOSE 8080

WORKDIR /app

# Prefer not to run as root.
USER deno

# Copy the server file
COPY server.js .

# Compile the main app so that it doesn't need to be compiled each startup/entry.
RUN deno cache server.js

# Run the server
CMD ["run", "--allow-net", "--allow-env", "server.js"]
