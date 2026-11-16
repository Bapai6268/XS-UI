package cmd

import (
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strconv"

	"github.com/alireza0/s-ui/database"
	"github.com/alireza0/s-ui/service"
)

// CLI only. No new HTTP endpoint, shell execution, password argument or log.
// The installer never starts the daemon unless this fresh-DB setup succeeds.
type quickInitOptions struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Port     int    `json:"port"`
	SubPort  int    `json:"sub_port"`
}

func quickInit(input io.Reader, dbPath string) error {
	var options quickInitOptions
	decoder := json.NewDecoder(io.LimitReader(input, 4097))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&options); err != nil {
		return errors.New("invalid setup JSON")
	}
	var extra interface{}
	if err := decoder.Decode(&extra); err != io.EOF {
		return errors.New("unexpected trailing input")
	}
	if !regexp.MustCompile(`^[a-zA-Z0-9_-]{4,32}$`).MatchString(options.Username) {
		return errors.New("invalid username")
	}
	if !regexp.MustCompile(`^[a-zA-Z0-9_-]{32,64}$`).MatchString(options.Password) {
		return errors.New("use a generated 32-64 character password")
	}
	if options.Port < 1024 || options.Port > 65535 || options.SubPort < 1024 || options.SubPort > 65535 || options.Port == options.SubPort {
		return errors.New("invalid panel ports")
	}
	if err := os.MkdirAll(filepath.Dir(dbPath), 0700); err != nil {
		return err
	}
	// Reserve atomically: repeated installation may never reset an existing DB.
	f, err := os.OpenFile(dbPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return errors.New("database already exists or cannot be created; refusing to overwrite")
	}
	if err = f.Close(); err != nil {
		return err
	}
	if err = database.InitDB(dbPath); err != nil {
		return err
	}
	users := service.UserService{}
	if err = users.UpdateFirstUser(options.Username, options.Password); err != nil {
		return err
	}
	settings := service.SettingService{}
	if _, err = settings.GetAllSetting(); err != nil {
		return err
	}
	data, err := json.Marshal(map[string]string{
		"webListen": "127.0.0.1", "subListen": "127.0.0.1",
		"webPort": strconv.Itoa(options.Port), "subPort": strconv.Itoa(options.SubPort),
		"webPath": "/app/", "sessionMaxAge": "60",
	})
	if err != nil {
		return err
	}
	return settings.Save(database.GetDB(), data)
}
