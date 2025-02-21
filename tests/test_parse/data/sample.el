;; Example Emacs Lisp file

(defun greet (name)
  "Say hello to NAME."
  (message "Hello, %s!" name))

(defvar *user-name* "World"
  "Default user name for greeting.")

(defmacro with-greeting (&rest body)
  "Execute BODY after greeting."
  `(progn
     (greet *user-name*)
     ,@body)) 