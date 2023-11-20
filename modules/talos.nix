flake: {
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (flake.packages.${pkgs.stdenv.hostPlatform.system}) CTO;
  inherit (lib) filterAttrs types mkEnableOption mkOption mkRenamedOptionModule;

  cfg = config.services.secondbrain.CTO;
in {
  options.services.secondbrain.CTO = {
    enable = mkEnableOption ''
      Talos: A multipurpose assistant Telegram bot.
    '';

    url = mkOption {
      type = types.str;
      description = ''
        Base URL to publish webhooks on.
      '';
    };

    port = mkOption {
      type = types.int;
      description = ''
        Port to run the server on.
      '';
    };

    tokenFile = mkOption {
      type = types.path;
      description = ''
        File containing the Telegram bot API token.
      '';
    };
  };
  config = lib.mkIf cfg.enable {
    users.users.CTO = {
      description = "secondbrain-CTO daemon user";
      isSystemUser = true;
      group = "CTO";
    };

    users.groups.CTO = {};

    systemd.services.CTO = {
      description = "secondbrain-CTO";

      after = ["network-online.target"];
      wantedBy = ["multi-user.target"];

      serviceConfig = {
        User = "CTO";
        Group = "CTO";
        Type = "oneshot";
        ExecStart =
          "${CTO}/bin/CTO "
          + "--calendar ${cfg.calendarURL} "
          + "--user ${cfg.username} "
          + "--password-file ${cfg.passwordFile} "
          + "--day-lookahead ${builtins.toString cfg.dayLookahead}";
      };
    };
    systemd.timers.CTO = {
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "*-*-* ${builtins.toString cfg.time.hour}:${builtins.toString cfg.time.minute}:00";
        Persistent = "True";
        Unit = "CTO.service";
      };
    };
  };
}
