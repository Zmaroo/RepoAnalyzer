#lang racket

;; Structure definition
(struct user (name age) #:transparent)

;; Contract definition
(provide/contract
 [create-user (-> string? integer? user?)]
 [process-user (-> user? (or/c string? false?))]
 [format-user (-> user? string?)])

;; Constructor with validation
(define (create-user name age)
  (cond
    [(< age 0) (error 'create-user "Age cannot be negative")]
    [(> age 150) (error 'create-user "Age cannot be greater than 150")]
    [else (user name age)]))

;; Function with pattern matching using match
(define (process-user u)
  (match u
    [(user _ age) #:when (< age 0) "Invalid age"]
    [(user _ age) #:when (< age 18) "Underage"]
    [(user name _) (format "Processing adult user: ~a" name)]))

;; Function with optional argument
(define (create-greeting name [prefix "Hello"])
  (format "~a, ~a!" prefix name))

;; Higher-order function
(define (process-users users proc)
  (map proc users))

;; Function returning function (closure)
(define (make-age-checker min-age)
  (λ (u)
    (>= (user-age u) min-age)))

;; Function using recursion
(define (find-user users name)
  (cond
    [(null? users) #f]
    [(string=? (user-name (car users)) name) (car users)]
    [else (find-user (cdr users) name)]))

;; Function using list comprehension
(define (get-adult-users users)
  (for/list ([u users]
             #:when (>= (user-age u) 18))
    u))

;; Function returning multiple values
(define (get-user-stats users)
  (let ([total (length users)]
        [adults (length (get-adult-users users))])
    (values total adults)))

;; Function using string manipulation
(define (format-user u)
  (format "~a (~a years old)" (user-name u) (user-age u)))

;; Function using hash tables
(define (create-user-registry)
  (make-hash))

(define (add-user-to-registry registry u)
  (hash-set! registry (user-name u) u))

(define (get-user-from-registry registry name)
  (hash-ref registry name #f))

;; Function using exceptions
(define (validate-user u)
  (with-handlers ([exn:fail? (λ (e) (exn-message e))])
    (cond
      [(string=? (user-name u) "") (error 'validate-user "Name cannot be empty")]
      [(< (user-age u) 0) (error 'validate-user "Age cannot be negative")]
      [else #t])))

;; Function using streams
(define (user-stream users)
  (stream-cons
   (car users)
   (if (null? (cdr users))
       empty-stream
       (user-stream (cdr users)))))

;; Function using continuations
(define (process-user/cc u success failure)
  (if (>= (user-age u) 18)
      (success (format "Adult user: ~a" (user-name u)))
      (failure (format "Minor user: ~a" (user-name u)))))

;; Function using macros
(define-syntax-rule (with-user name age body ...)
  (let ([u (create-user name age)])
    body ...))

;; Main execution function
(define (main)
  (printf "Creating users...\n")
  (define users
    (list (create-user "John" 25)
          (create-user "Alice" 17)))
  
  ;; Test basic functions
  (printf "\nUsers:\n")
  (for-each (λ (u) (printf "~a\n" (format-user u))) users)
  
  ;; Test processing
  (printf "\nProcessing results:\n")
  (for-each (λ (result) (printf "~a\n" result))
            (process-users users process-user))
  
  ;; Test user stats
  (printf "\nUser statistics:\n")
  (let-values ([(total adults) (get-user-stats users)])
    (printf "Total users: ~a\n" total)
    (printf "Adult users: ~a\n" adults))
  
  ;; Test user finding
  (printf "\nFinding user:\n")
  (let ([found (find-user users "John")])
    (when found
      (printf "Found: ~a\n" (format-user found))))
  
  ;; Test registry
  (printf "\nTesting registry:\n")
  (define registry (create-user-registry))
  (for-each (λ (u) (add-user-to-registry registry u)) users)
  (let ([found (get-user-from-registry registry "John")])
    (when found
      (printf "Found in registry: ~a\n" (format-user found))))
  
  ;; Test streams
  (printf "\nTesting streams:\n")
  (let ([s (user-stream users)])
    (stream-for-each
     (λ (u) (printf "Stream user: ~a\n" (format-user u)))
     s))
  
  ;; Test continuations
  (printf "\nTesting continuations:\n")
  (for-each
   (λ (u)
     (process-user/cc
      u
      (λ (success) (printf "Success: ~a\n" success))
      (λ (failure) (printf "Failure: ~a\n" failure))))
   users)
  
  ;; Test macro
  (printf "\nTesting macro:\n")
  (with-user "Bob" 30
    (printf "Created user: ~a\n" (format-user u)))
  
  ;; Test validation
  (printf "\nTesting validation:\n")
  (for-each
   (λ (u)
     (let ([result (validate-user u)])
       (printf "Validation result for ~a: ~a\n"
               (user-name u)
               (if (eq? result #t) "valid" result))))
   users))

;; Run main if this is the main module
(module+ main
  (main)) 