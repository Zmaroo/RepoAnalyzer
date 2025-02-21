package main

type Server struct {
    port int
}

func NewServer(port int) *Server {
    return &Server{port: port}
}

func (s *Server) Start() error {
    return nil
} 