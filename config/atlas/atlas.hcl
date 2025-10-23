env "local" {
  url = getenv("DB_URL")
  src = "file://schema"
  dev = "docker://postgres/17/dev?search_path=public"
  migration {
    dir = "file://migrations"
  }
}
