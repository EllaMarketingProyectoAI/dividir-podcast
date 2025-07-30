{ pkgs }: {
  deps = [
    pkgs.ffmpeg
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.requests
    pkgs.python311Packages.python-dotenv
  ];
}
