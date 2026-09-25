# Sourced by the launch scripts: load .env into the environment.
# read .env as KEY=VALUE settings, not as a shell script: a value with spaces
# (STOCKSKILL_OPERATOR=SMI Investments) must not be run as a command
load_env() {
  local line key val
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"; val="${line#*=}"
    key="${key#export }"; key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    [ "$key" = "$line" ] && continue
    val="${val#"${val%%[![:space:]]*}"}"; val="${val%"${val##*[![:space:]]}"}"
    if [[ "$val" == \"*\" || "$val" == \'*\' ]]; then val="${val:1:${#val}-2}"; fi
    export "$key=$val"
  done < .env
}
