package main

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/creack/pty"
	_ "github.com/go-sql-driver/mysql"
)

const (
	MySQLPrefix = "mysql> "
	RetryTime   = 3
	TaskStart   = "executing"
	TaskFailed  = "failed"
	TaskSuccess = "success"
	Pause       = "pause"
)

type LocalCommand struct {
	command string
	argv    []string

	cmd       *exec.Cmd
	ptyFd     *os.File
	ptyClosed chan struct{}

	ptyWin *pty.Winsize
}

func NewLocalCommand(command string, argv []string) (*LocalCommand, error) {
	ptyClosed := make(chan struct{})
	lCmd := &LocalCommand{
		command:   command,
		argv:      argv,
		ptyClosed: ptyClosed,
	}

	cmd := exec.Command(command, argv...)
	ptyFd, err := pty.StartWithSize(cmd, lCmd.ptyWin)
	if err != nil {
		return nil, fmt.Errorf("%w", err)
	}
	lCmd.cmd = cmd
	lCmd.ptyFd = ptyFd
	go func() {
		defer func() {
			_ = lCmd.ptyFd.Close()
			close(lCmd.ptyClosed)
		}()
		_ = lCmd.cmd.Wait()
	}()

	return lCmd, nil
}

func (lCmd *LocalCommand) Read(p []byte) (n int, err error) {
	return lCmd.ptyFd.Read(p)
}

func (lCmd *LocalCommand) Write(p []byte) (n int, err error) {
	return lCmd.ptyFd.Write(p)
}

func (lCmd *LocalCommand) Close() error {
	select {
	case <-lCmd.ptyClosed:
		return nil
	default:
		if lCmd.cmd != nil && lCmd.cmd.Process != nil {
			return lCmd.cmd.Process.Signal(syscall.SIGKILL)
		}
	}
	return nil
}

func (lCmd *LocalCommand) SetWinSize(width int, height int) error {
	win := pty.Winsize{
		Rows: uint16(height),
		Cols: uint16(width),
	}
	return pty.Setsize(lCmd.ptyFd, &win)
}

type BaseHandler interface {
	Connect() error
	DoCommand(command string) (string, error)
	Close()
}

type ScriptHandler struct {
	opts CmdOptions

	lCmd *LocalCommand
}

func (s *ScriptHandler) Connect() error {
	lCmd, _ := NewLocalCommand(s.opts.Script, s.opts.ScriptArgs)
	s.lCmd = lCmd

	time.Sleep(time.Second * 1)
	prompt := make([]byte, 1024)
	for {
		n, _ := lCmd.Read(prompt)
		if strings.Contains(string(prompt[:n]), MySQLPrefix) {
			break
		}
	}
	return nil
}

func (s *ScriptHandler) DoCommand(command string) (string, error) {
	result := ""
	_, err := s.lCmd.Write([]byte(command + "\n"))
	if err != nil {
		return "", err
	}
	for {
		r := make([]byte, 1024)
		n, _ := s.lCmd.Read(r)
		line := string(r[:n])
		if strings.Contains(line, MySQLPrefix) {
			break
		}
		result += string(r[:n])
	}
	return result, nil
}

func (s *ScriptHandler) Close() {
	_ = s.lCmd.Close()
}

type MySQLHandler struct {
	opts CmdOptions

	db *sql.DB
}

func (s *MySQLHandler) Connect() error {
	dsn := fmt.Sprintf(
		"%s:%s@tcp(%s:%v)/%s", s.opts.Auth.Username, s.opts.Auth.Password,
		s.opts.Auth.Address, s.opts.Auth.Port, s.opts.Auth.DBName,
	)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return err
	}
	if err = db.Ping(); err != nil {
		return err
	}
	s.db = db
	return nil
}

func (s *MySQLHandler) DoCommand(command string) (string, error) {
	r, err := s.db.Exec(command)
	if err != nil {
		return "", err
	}
	affected, _ := r.RowsAffected()
	return fmt.Sprintf("Affected rows: %v", affected), nil
}

func (s *MySQLHandler) Close() {
	_ = s.db.Close()
}

func getHandler(opts CmdOptions) BaseHandler {
	switch opts.CmdType {
	case "mysql":
		return &MySQLHandler{opts: opts}
	case "script":
		return &ScriptHandler{opts: opts}
	}
	return nil
}

type Cmd struct {
	ID       string `json:"id"`
	Value    string `json:"input"`
	Index    int    `json:"index"`
	Category string `json:"category"`
}

type Auth struct {
	Address  string `json:"address"`
	Port     int    `json:"port"`
	Username string `json:"username"`
	Password string `json:"password"`
	DBName   string `json:"db_name"`
}

type CmdOptions struct {
	CommandBase64 string `json:"-"`
	Backend       bool   `json:"-"`

	TaskID      string   `json:"task_id"`
	Host        string   `json:"host"`
	Token       string   `json:"token"`
	OrgId       string   `json:"org_id"`
	Script      string   `json:"script"`
	ScriptArgs  []string `json:"script_args"`
	Auth        Auth     `json:"auth"`
	CmdType     string   `json:"cmd_type"`
	CmdFilepath string   `json:"cmd_filepath"`
	CmdSet      []Cmd    `json:"command_set"`
	Encrypted   bool     `json:"encrypted_data"`
}

func (co *CmdOptions) ValidCmdType() bool {
	validType := []string{"mysql", "oracle", "script"}
	for _, vType := range validType {
		if co.CmdType == vType {
			return true
		}
	}
	return false
}

func (co *CmdOptions) aesCBCDecrypt(ciphertext []byte) ([]byte, error) {
	block, err := aes.NewCipher([]byte(co.Token[:32]))
	if err != nil {
		return nil, err
	}

	padding := len(ciphertext) % aes.BlockSize
	if padding > 0 {
		ciphertext = ciphertext[:len(ciphertext)-padding]
	}

	mode := cipher.NewCBCDecrypter(block, ciphertext[:aes.BlockSize])
	plaintext := make([]byte, len(ciphertext)-aes.BlockSize)
	mode.CryptBlocks(plaintext, ciphertext[aes.BlockSize:])
	return plaintext, nil
}

func (co *CmdOptions) ParseCmdFile() error {
	if _, err := os.Stat(co.CmdFilepath); err != nil {
		return fmt.Errorf("命令文件不存在: %s", err)
	}

	text, err := os.ReadFile(co.CmdFilepath)
	if err != nil {
		return fmt.Errorf("读取命令文件内容失败: %s", err)
	}
	if co.Encrypted {
		if text, err = co.aesCBCDecrypt(text); err != nil {
			return err
		}
	}
	err = json.Unmarshal(text, &co)
	if err != nil {
		return err
	}
	return nil
}

func (co *CmdOptions) Valid() error {
	rawCommand, err := base64.StdEncoding.DecodeString(co.CommandBase64)
	if err != nil {
		return err
	}

	if err = json.Unmarshal(rawCommand, &co); err != nil {
		return err
	}

	if err = co.ParseCmdFile(); err != nil {
		return fmt.Errorf("命令集合解析失败: %s", err)
	}

	if ok := co.ValidCmdType(); !ok {
		return fmt.Errorf("不支持的命令类型: %s", co.CmdType)
	}
	return nil
}

type JumpServerClient struct {
	host  string
	token string
	orgId string

	client *http.Client
	logger *log.Logger
}

func NewJMSClient(host, token, orgId string, logger *log.Logger) *JumpServerClient {
	return &JumpServerClient{
		host: host, token: token, orgId: orgId,
		logger: logger, client: &http.Client{},
	}
}

func (c *JumpServerClient) Get(url string) ([]byte, error) {
	request, err := http.NewRequest("GET", c.host+url, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Add("Authorization", c.token)
	resp, err := c.client.Do(request)
	if err != nil {
		return nil, err
	}
	defer func(Body io.ReadCloser) {
		_ = Body.Close()
	}(resp.Body)

	body, _ := io.ReadAll(resp.Body)
	return body, nil
}

func (c *JumpServerClient) Post(url string, data map[string]interface{}) (*http.Response, error) {
	byteData, _ := json.Marshal(data)
	request, err := http.NewRequest(
		"POST", c.host+url, bytes.NewBuffer(byteData),
	)
	if err != nil {
		return nil, err
	}
	request.Header.Add("Authorization", "Bearer "+c.token)
	request.Header.Add("X-JMS-ORG", c.orgId)
	request.Header.Set("Content-Type", "application/json")
	resp, err := c.client.Do(request)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

type TaskResponse struct {
	Status bool   `json:"status"`
	Detail string `json:"detail"`
}

func (c *JumpServerClient) HealthFeedback(taskID string) {
	var err error
	data := make(map[string]interface{})
	data["action"] = "health"

	url := fmt.Sprintf("/api/v1/behemoth/executions/%s/?type=health", taskID)
	for i := 0; i < RetryTime; i++ {
		_, err = c.Post(url, data)
		if err == nil {
			break
		}
		c.logger.Printf("%s, Task[%s] running health.", time.Now(), taskID)
		time.Sleep(10 * time.Second)
	}
}

func (c *JumpServerClient) OperateTask(taskID, status string, err error) error {
	data := make(map[string]interface{})
	data["status"] = status
	if err != nil {
		data["reason"] = err.Error()
	} else {
		data["reason"] = "-"
	}

	url := fmt.Sprintf("/api/v1/behemoth/executions/%s/?type=status", taskID)
	resp, err := c.Post(url, data)
	if err != nil {
		c.logger.Printf("Task[%s] running operation failed, %s", taskID, err)
		return err
	}

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		defer func(body io.ReadCloser) {
			_ = body.Close()
		}(resp.Body)
		return fmt.Errorf(string(body))
	}
	if status == TaskStart {
		//go c.HealthFeedback(taskID)
	}
	return nil
}

func (c *JumpServerClient) CommandCB(
	taskID string, command *Cmd, result string, err error,
) (*TaskResponse, error) {

	data := make(map[string]interface{})
	data["command_id"] = command.ID
	data["timestamp"] = time.Now().Unix()
	if err == nil {
		data["status"] = "success"
		data["output"] = result
	} else {
		data["status"] = "failed"
		data["output"] = err.Error()
	}
	url := fmt.Sprintf("/api/v1/behemoth/executions/%s/?type=command", taskID)
	resp, err := c.Post(url, data)
	if err != nil {
		return nil, err
	}

	body, _ := io.ReadAll(resp.Body)
	defer func(body io.ReadCloser) {
		_ = body.Close()
	}(resp.Body)

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf(string(body))
	}

	var response TaskResponse
	err = json.Unmarshal(body, &response)
	if err != nil {
		return nil, fmt.Errorf(string(body))
	}
	return &response, nil
}

func ensureDirExists(path string) {
	_, err := os.Stat(path)
	if os.IsNotExist(err) {
		// 如果路径不存在，则创建
		_ = os.MkdirAll(path, os.ModePerm)
	}
}

func GetLogger(taskId string) *log.Logger {
	logDir := "/tmp/behemoth/logs"
	ensureDirExists(logDir)
	logFile := filepath.Join(logDir, fmt.Sprintf("%v-bs.log", taskId))
	f, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err != nil {
		fmt.Printf("Error opening file: %v", err)
	}
	return log.New(f, "", log.Ldate|log.Ltime|log.Lshortfile)
}

func main() {
	opts := CmdOptions{}
	flag.StringVar(&opts.CommandBase64, "command", opts.CommandBase64, "命令")
	flag.BoolVar(&opts.Backend, "backend", false, "后台")
	// 解析命令行标志
	flag.Parse()

	if opts.Backend {
		cmd := exec.Command(os.Args[0], "--command", opts.CommandBase64)
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
		_ = cmd.Start()
		os.Exit(0)
	}
	if err := opts.Valid(); err != nil {
		fmt.Printf("参数校验错误: %v\n", err)
		return
	}

	logger := GetLogger(opts.TaskID)
	jmsClient := NewJMSClient(opts.Host, opts.Token, opts.OrgId, logger)

	logger.Printf("Start executing the task")
	if err := jmsClient.OperateTask(opts.TaskID, TaskStart, nil); err != nil {
		logger.Fatalf("Task launch failed: %v\n", err)
	}
	handler := getHandler(opts)
	if err := handler.Connect(); err != nil {
		_ = jmsClient.OperateTask(opts.TaskID, TaskFailed, err)
		logger.Fatalf("Task connect failed: %v\n", err)
	}

	var result string
	var err error
	for _, command := range opts.CmdSet {
		if command.Category == Pause {
			result, err = "", nil
		} else {
			result, err = handler.DoCommand(command.Value)
		}
		time.Sleep(2 * time.Second)
		resp, err := jmsClient.CommandCB(opts.TaskID, &command, result, err)
		if err != nil {
			logger.Fatalf("Command callback failed: %v\n", err)
		}
		if !resp.Status {
			logger.Printf(
				"Not allow to continue executing commands[Input: %v, error: %v]", command.Value, resp.Detail,
			)
			logger.Printf("Task finished.")
			return
		}
	}
	_ = jmsClient.OperateTask(opts.TaskID, TaskSuccess, nil)
	logger.Printf("Task finished successfully")
}
