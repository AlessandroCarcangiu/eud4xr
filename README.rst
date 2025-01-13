- How to install Home Assistant developer?

1) Install docker;
2) Install Visual Studio;
3) Set up development environment.
   Follow the instructions in the "Getting started" section, https://developers.home-assistant.io/docs/development_environment/,
   skipping the first point: instead of creating a new fork, insert the url of this repository (https://github.com/AlessandroCarcangiu/eud4xr).


- How to start Home Assistant server?
From Visual Studio, select Tasks: Run Task -> Run Home Assistant Core

- How to make the chatbot communicate with the Home Assistant server?
Make sure both servers are running.

NB this repository includes a configuration.yaml file that recreates a simple virtual scene containing eca scripts.

- How to make the Home Assistant server communicate with the Unity application?
   If you're launching the Unity application in playmode, to start communication with the Home Assistant server follow these steps:
   1) start NGROK to publicly expose the port used by the server launched by the Unity application, typically port 8080.
      To do this, download NGROK and create a new account. Here you can decide whether to create a new domain, so that ngrok
      always uses the same url as tunnel, or use a new different url every time it is started.

      If you decide to create a new domain, from the NGROK terminal launch this command:
      ngrok http 8080 --host-header="localhost:8080" --domain="your_domain_address"
      Example: ngrok http 8080 --host-header="localhost:8080" --domain="fly-powerful-slug.ngrok-free.app"

      Otherwise: ngrok http 8080 --host-header="localhost:8080"
      then copy the url that will act as tunnel.

      Alternative: find a way to communicate with the docker container running the Home Assistant server.

   2) Once NGROK is started, in the configuration.yaml replace the value associated with the 'server_unity_url' key, inside the 'eud4xr' section,
      with your domain, e.g. "fly-powerful-slug.ngrok-free.app", or with the url that NGROK has automatically assigned to you.

   3) Start Home Assistant.

   4) Start Unity.

   NB it's important that Unity is started only after Home Assistant, to allow the registration of all pairs (game object-eca script) present in the virtual scene.