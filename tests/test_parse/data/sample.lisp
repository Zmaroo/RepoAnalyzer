;; Define package
(defpackage :user-manager
  (:use :cl)
  (:export :make-user
           :process-user
           :user-name
           :user-age))

(in-package :user-manager)

;; Define user class
(defclass user ()
  ((name
    :initarg :name
    :accessor user-name
    :type string)
   (age
    :initarg :age
    :accessor user-age
    :type integer)))

;; Constructor function
(defun make-user (name age)
  (make-instance 'user :name name :age age))

;; Generic function
(defgeneric process-user (user)
  (:documentation "Process a user based on their age"))

;; Method implementation
(defmethod process-user ((user user))
  (with-slots (name age) user
    (cond
      ((< age 0) (error "Invalid age"))
      ((< age 18) (values nil "Underage"))
      (t (values t "Adult")))))

;; Function with optional parameters
(defun create-greeting (name &optional (prefix "Hello"))
  (format nil "~A, ~A!" prefix name))

;; Function with keyword parameters
(defun format-user (user &key (verbose nil))
  (with-slots (name age) user
    (if verbose
        (format nil "User ~A is ~D years old" name age)
        (format nil "~A (~D)" name age))))

;; Higher-order function
(defun process-users (users processor)
  (mapcar processor users))

;; Closure returning function
(defun make-age-checker (min-age)
  (lambda (user)
    (>= (user-age user) min-age)))

;; Recursive function
(defun find-user (name users)
  (cond
    ((null users) nil)
    ((string= name (user-name (car users))) (car users))
    (t (find-user name (cdr users)))))

;; Macro definition
(defmacro with-user ((var name age) &body body)
  `(let ((,var (make-user ,name ,age)))
     ,@body))

;; Function using multiple values
(defun analyze-user (user)
  (multiple-value-bind (valid message)
      (process-user user)
    (if valid
        (format nil "Valid user: ~A" message)
        (format nil "Invalid user: ~A" message))))

;; List processing function
(defun get-adult-users (users)
  (remove-if-not (make-age-checker 18) users))

;; Function with type declarations
(declaim (ftype (function (user) string) get-uppercase-name))
(defun get-uppercase-name (user)
  (declare (type user user))
  (string-upcase (user-name user)))

;; Main execution function
(defun run-examples ()
  ;; Create test users
  (let* ((user1 (make-user "John" 25))
         (user2 (make-user "Alice" 17))
         (users (list user1 user2)))
    
    ;; Test basic functions
    (format t "User 1: ~A~%" (format-user user1))
    (format t "User 2: ~A~%" (format-user user2))
    
    ;; Test processing
    (format t "Processing results:~%")
    (dolist (user users)
      (format t "~A: ~A~%" 
              (user-name user)
              (analyze-user user)))
    
    ;; Test higher-order functions
    (format t "Adult users:~%")
    (dolist (user (get-adult-users users))
      (format t "~A~%" (format-user user)))
    
    ;; Test macro
    (with-user (test-user "Bob" 30)
      (format t "Created test user: ~A~%" 
              (format-user test-user)))
    
    ;; Test closure
    (let ((is-adult (make-age-checker 18)))
      (format t "Is user1 adult? ~A~%" 
              (if (funcall is-adult user1) "Yes" "No")))
    
    ;; Test type-declared function
    (format t "Uppercase name: ~A~%" 
            (get-uppercase-name user1))))

;; Run examples
(run-examples) 