package cmd

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/alireza0/s-ui/service"
	"github.com/alireza0/s-ui/util"
)

func TestQuickInitPrivateAndNoOverwrite(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "s-ui.db")
	input := `{"username":"test-admin","password":"0123456789abcdef0123456789abcdef","port":2095,"sub_port":2096}`
	if err := quickInit(strings.NewReader(input), dbPath); err != nil {
		t.Fatal(err)
	}
	s := service.SettingService{}
	settings, err := s.GetAllSetting()
	if err != nil {
		t.Fatal(err)
	}
	if (*settings)["webListen"] != "127.0.0.1" || (*settings)["subListen"] != "127.0.0.1" {
		t.Fatal("panel must be private")
	}
	u := service.UserService{}
	user, err := u.GetFirstUser()
	if err != nil {
		t.Fatal(err)
	}
	if user.Username != "test-admin" || !util.IsHashedPassword(user.Password) || !util.CheckPassword("0123456789abcdef0123456789abcdef", user.Password) {
		t.Fatal("credentials not secured")
	}
	if err = quickInit(strings.NewReader(input), dbPath); err == nil {
		t.Fatal("must refuse existing DB")
	}
}

func TestQuickInitRejectsInvalidInputBeforeDB(t *testing.T) {
	for _, input := range []string{
		`{"username":"test-admin","password":"admin","port":2095,"sub_port":2096}`,
		`{"username":"test-admin","password":"0123456789abcdef0123456789abcdef","port":2095,"sub_port":2095}`,
		`{"username":"test-admin","password":"0123456789abcdef0123456789abcdef","port":2095,"sub_port":2096,"command":"sh"}`,
		`{} {}`,
	} {
		if err := quickInit(strings.NewReader(input), filepath.Join(t.TempDir(), "s-ui.db")); err == nil {
			t.Fatal("accepted invalid input")
		}
	}
}
