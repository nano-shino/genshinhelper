{ pkgs }: {
	deps = [
        pkgs.bashInteractive
		pkgs.python39Full
		pkgs.python39Packages.pip
	];
}
