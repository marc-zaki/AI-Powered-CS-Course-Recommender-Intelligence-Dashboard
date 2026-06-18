LOCAL_QUIZ_BANK = {
    "artificial intelligence": {
        "beginner": [
            {
                "id": 1,
                "question": "What is the primary goal of Machine Learning?",
                "options": [
                    "To create static webpages",
                    "To enable computers to learn from data without explicit programming",
                    "To design high-speed processors",
                    "To manage relational databases"
                ],
                "correct_index": 1,
                "explanation": "Machine learning focuses on algorithms that allow systems to learn patterns from data and make decisions."
            },
            {
                "id": 2,
                "question": "Which of the following is a type of Supervised Learning?",
                "options": [
                    "Clustering",
                    "Dimensionality Reduction",
                    "Classification",
                    "Anomaly Detection"
                ],
                "correct_index": 2,
                "explanation": "Classification (like email spam detection) is supervised learning because the training data is labeled."
            },
            {
                "id": 3,
                "question": "What does 'Neural Network' in AI draw inspiration from?",
                "options": [
                    "Computer network routers",
                    "The human brain's network of neurons",
                    "Social media friend networks",
                    "Electrical power grids"
                ],
                "correct_index": 1,
                "explanation": "Artificial Neural Networks are loosely inspired by the structure and biological processing of human brain neurons."
            },
            {
                "id": 4,
                "question": "What is the role of training data in AI?",
                "options": [
                    "To store the final output of the program",
                    "To display charts to users",
                    "To teach the AI model and adjust its parameters",
                    "To compile the source code"
                ],
                "correct_index": 2,
                "explanation": "Training data is used by machine learning algorithms to learn weights, patterns, and representations."
            },
            {
                "id": 5,
                "question": "Which of these is a common programming language used in AI development?",
                "options": [
                    "HTML",
                    "SQL",
                    "Python",
                    "Assembly"
                ],
                "correct_index": 2,
                "explanation": "Python is the most popular language for AI due to its rich library ecosystem (TensorFlow, PyTorch, Scikit-learn)."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What is the purpose of the 'Activation Function' in a Neural Network?",
                "options": [
                    "To compile the neural network code",
                    "To introduce non-linearity into the network",
                    "To clean training datasets",
                    "To speed up database search queries"
                ],
                "correct_index": 1,
                "explanation": "Without activation functions (like ReLU or Sigmoid), a neural network would just be a linear regression model, unable to learn complex patterns."
            },
            {
                "id": 2,
                "question": "What is the difference between Supervised and Unsupervised Learning?",
                "options": [
                    "Supervised uses labeled data, whereas unsupervised uses unlabeled data",
                    "Supervised is faster, unsupervised is slower",
                    "Unsupervised is only for neural networks",
                    "Supervised does not use algorithms"
                ],
                "correct_index": 0,
                "explanation": "Supervised learning relies on pairs of input-labeled outputs, while unsupervised learning uncovers hidden structures in unlabeled datasets."
            },
            {
                "id": 3,
                "question": "What is overfitting in machine learning?",
                "options": [
                    "When a model performs well on training data but poorly on unseen test data",
                    "When a model is too small to fit the memory",
                    "When training takes too long to execute",
                    "When the data has too many columns"
                ],
                "correct_index": 0,
                "explanation": "Overfitting happens when a model learns the training data's noise and details too well, failing to generalize to new, unseen data."
            },
            {
                "id": 4,
                "question": "What does a Decision Tree split data based on?",
                "options": [
                    "Random coin flips",
                    "Feature values that maximize information gain or minimize impurity",
                    "The chronological order of data points",
                    "ASCII character values"
                ],
                "correct_index": 1,
                "explanation": "Decision trees split nodes based on features that maximize metrics like Information Gain (using Entropy) or Gini Impurity."
            },
            {
                "id": 5,
                "question": "What is 'Gradient Descent'?",
                "options": [
                    "An optimization algorithm used to minimize a loss function",
                    "A sorting algorithm for large arrays",
                    "A data visualization charting technique",
                    "A method for secure network routing"
                ],
                "correct_index": 0,
                "explanation": "Gradient Descent is an optimization algorithm that iteratively adjusts parameters to find the minimum of a cost/loss function."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "In Transformer architectures, what is the primary purpose of the 'Self-Attention' mechanism?",
                "options": [
                    "To compress the input tokens into a single vector representation",
                    "To relate different positions of a single sequence to compute a representation of the sequence",
                    "To speed up CPU multi-threading during training",
                    "To eliminate the need for backpropagation"
                ],
                "correct_index": 1,
                "explanation": "Self-attention allows the model to look at other words in the input sequence to better understand each word in context."
            },
            {
                "id": 2,
                "question": "What problem does 'Backpropagation Through Time' (BPTT) face in deep RNNs?",
                "options": [
                    "Deadlock conditions",
                    "Vanishing and exploding gradients",
                    "Memory fragmentation",
                    "Infinite recursion compiler crashes"
                ],
                "correct_index": 1,
                "explanation": "Due to the long sequence lengths, gradients multiplied repeatedly over time steps tend to either exponentially vanish or explode."
            },
            {
                "id": 3,
                "question": "What is the key idea behind Generative Adversarial Networks (GANs)?",
                "options": [
                    "Two databases merging with conflict resolution",
                    "A generator and a discriminator network competing in a minimax game",
                    "Parallel execution of multiple regression models",
                    "Strict rule-based expert systems"
                ],
                "correct_index": 1,
                "explanation": "GANs consist of a generator creating fake data and a discriminator trying to detect fakes, training each other through competition."
            },
            {
                "id": 4,
                "question": "Which regularization technique randomly drops connections between neural units during training?",
                "options": [
                    "L2 Weight Decay",
                    "Batch Normalization",
                    "Dropout",
                    "Early Stopping"
                ],
                "correct_index": 2,
                "explanation": "Dropout randomly sets a fraction of input units to 0 at each update during training, which prevents co-adaptation of feature detectors."
            },
            {
                "id": 5,
                "question": "What does the 'Q' represent in Q-Learning (Reinforcement Learning)?",
                "options": [
                    "Queue size",
                    "Quality (expected utility of a state-action pair)",
                    "Query latency",
                    "Quantum state"
                ],
                "correct_index": 1,
                "explanation": "Q stands for Quality, representing the expected long-term reward of taking a specific action in a given state."
            }
        ]
    },
    "web development": {
        "beginner": [
            {
                "id": 1,
                "question": "What is the primary language used to define the style and layout of a webpage?",
                "options": ["HTML", "XML", "CSS", "SQL"],
                "correct_index": 2,
                "explanation": "CSS (Cascading Style Sheets) is designed to separate the presentation of a document from its structure (defined in HTML)."
            },
            {
                "id": 2,
                "question": "Which HTML tag is used to create a hyperlink?",
                "options": ["<link>", "<a>", "<href>", "<nav>"],
                "correct_index": 1,
                "explanation": "The <a> (anchor) tag is used to define hyperlinks linking one page to another."
            },
            {
                "id": 3,
                "question": "What does DOM stand for in Web Development?",
                "options": [
                    "Document Object Model",
                    "Data Object Management",
                    "Domain Outline Mapping",
                    "Digital Ordinance Matrix"
                ],
                "correct_index": 0,
                "explanation": "DOM stands for Document Object Model, which represents the page structure so that programs can change the document structure, style, and content."
            },
            {
                "id": 4,
                "question": "Which CSS property is used to change the text color of an element?",
                "options": ["font-color", "text-color", "color", "background-color"],
                "correct_index": 2,
                "explanation": "The 'color' property in CSS specifies the text color of an element."
            },
            {
                "id": 5,
                "question": "What is the primary purpose of JavaScript in a standard webpage?",
                "options": [
                    "To store user credentials on the database",
                    "To compile HTML templates",
                    "To add interactivity, behavior, and dynamic content to a webpage",
                    "To design graphics and logos"
                ],
                "correct_index": 2,
                "explanation": "JavaScript is a client-side scripting language that enables interactive elements, animations, and dynamic updates."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What is a major difference between HTTP GET and POST methods?",
                "options": [
                    "GET requests can send parameters in the request body, while POST cannot",
                    "GET is used to retrieve data, whereas POST is used to submit data to be processed",
                    "GET is secure by default, while POST is not",
                    "POST is only compatible with XML data formats"
                ],
                "correct_index": 1,
                "explanation": "GET requests are designed to retrieve data and append parameters to the URL. POST requests submit data, typically in the request body, to create/update resources."
            },
            {
                "id": 2,
                "question": "What is the purpose of 'localStorage' in browser storage APIs?",
                "options": [
                    "To cache images on a proxy server",
                    "To store key-value data locally with no expiration date",
                    "To store temporary session variables that expire when the tab closes",
                    "To sync database transactions in real-time"
                ],
                "correct_index": 1,
                "explanation": "localStorage stores data with no expiration time, whereas sessionStorage clears data when the page session ends (tab closes)."
            },
            {
                "id": 3,
                "question": "In JavaScript, what is a closure?",
                "options": [
                    "A method of ending an infinite loop",
                    "A function that has access to its outer lexical scope even after the outer function has executed",
                    "A method for closing database connections",
                    "An event handler that stops event propagation"
                ],
                "correct_index": 1,
                "explanation": "A closure is the combination of a function bundled together with references to its surrounding state (lexical environment)."
            },
            {
                "id": 4,
                "question": "What is the virtual DOM in modern frameworks like React?",
                "options": [
                    "An exact replica of the browser's window object",
                    "A lightweight, virtual representation of the real DOM in memory used to calculate efficient updates",
                    "A server-side cache for HTML pages",
                    "A browser extension that debugs web applications"
                ],
                "correct_index": 1,
                "explanation": "React uses a virtual DOM to determine the minimum number of changes needed (reconciliation) before updating the actual browser DOM, improving performance."
            },
            {
                "id": 5,
                "question": "What does CORS stand for?",
                "options": [
                    "Cross-Origin Resource Sharing",
                    "Client-Oriented Routing System",
                    "Core Object Request Service",
                    "Compiled Object Responsive Styles"
                ],
                "correct_index": 0,
                "explanation": "CORS (Cross-Origin Resource Sharing) is a browser security mechanism that uses headers to allow or restrict resources requested from other domains."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "What is the core difference between Server-Side Rendering (SSR) and Client-Side Rendering (CSR)?",
                "options": [
                    "SSR only runs on SQL databases, while CSR runs on MongoDB",
                    "SSR pre-renders HTML on the server for each request, while CSR renders the UI dynamically in the browser using JavaScript",
                    "SSR is always slower to load the first paint than CSR",
                    "CSR is executed on a Content Delivery Network (CDN) only"
                ],
                "correct_index": 1,
                "explanation": "SSR parses page content on the server and delivers fully populated HTML to the browser, while CSR delivers an empty container and renders page content via client-side JavaScript."
            },
            {
                "id": 2,
                "question": "What is the goal of optimizing the 'Critical Rendering Path' in a web application?",
                "options": [
                    "To secure database queries from SQL injection",
                    "To minimize the time the browser takes to process and paint HTML, CSS, and JS onto the screen",
                    "To design better routing algorithms",
                    "To compile TypeScript files into JavaScript faster"
                ],
                "correct_index": 1,
                "explanation": "Critical Rendering Path optimization reduces render-blocking resources so the browser can display the page to the user as fast as possible."
            },
            {
                "id": 3,
                "question": "How does HTTP/2 improve loading performance compared to HTTP/1.1?",
                "options": [
                    "It replaces TCP with UDP completely",
                    "It introduces multiplexing, allowing multiple request/response cycles over a single TCP connection",
                    "It disallows cookie headers to compress size",
                    "It encrypts all data automatically without needing SSL certificates"
                ],
                "correct_index": 1,
                "explanation": "HTTP/2 introduces multiplexing, header compression, and server push, allowing browsers to request multiple files simultaneously over one connection."
            },
            {
                "id": 4,
                "question": "What is the WebSockets protocol used for?",
                "options": [
                    "Encrypting email notifications",
                    "Enabling full-duplex, persistent communication channels between client and server",
                    "Mapping domain names to server IP addresses",
                    "Downloading binary zip files faster"
                ],
                "correct_index": 1,
                "explanation": "WebSockets establish a continuous, bidirectional connection suitable for real-time web applications like chat or collaborative tools."
            },
            {
                "id": 5,
                "question": "What is Cross-Site Scripting (XSS)?",
                "options": [
                    "An attack where a user is forced to execute actions they didn't intend to",
                    "A vulnerability allowing malicious scripts to be injected into trusted websites and executed in the client's browser",
                    "An exploit targeting database servers by bypassing firewalls",
                    "A method for intercepting network packets in transit"
                ],
                "correct_index": 1,
                "explanation": "XSS allows attackers to inject client-side scripts (usually JavaScript) into web pages viewed by other users, potentially stealing cookies, tokens, or sensitive information."
            }
        ]
    },
    "data science": {
        "beginner": [
            {
                "id": 1,
                "question": "Which Python library is the standard for data manipulation and analysis?",
                "options": ["Django", "NumPy", "Pandas", "Flask"],
                "correct_index": 2,
                "explanation": "Pandas is the leading Python package for structured data manipulation, providing the powerful DataFrame object."
            },
            {
                "id": 2,
                "question": "What is a DataFrame in Pandas?",
                "options": [
                    "A single-dimensional array of numbers",
                    "A 2D, size-mutable, tabular data structure with labeled axes (rows and columns)",
                    "A connection object to a PostgreSQL database",
                    "A layout model for CSS formatting"
                ],
                "correct_index": 1,
                "explanation": "A DataFrame is a two-dimensional, tabular data structure resembling a spreadsheet or SQL table."
            },
            {
                "id": 3,
                "question": "In statistics, what is the 'Mean' of a dataset?",
                "options": [
                    "The middle value when the data is sorted",
                    "The average calculated by summing all values and dividing by the total count",
                    "The most frequently occurring value",
                    "The difference between the highest and lowest values"
                ],
                "correct_index": 1,
                "explanation": "The mean is the arithmetic average of a set of numbers."
            },
            {
                "id": 4,
                "question": "What type of chart is best suited to visualize the relationship between two continuous variables?",
                "options": ["Pie Chart", "Bar Chart", "Scatter Plot", "Histogram"],
                "correct_index": 2,
                "explanation": "A scatter plot plots individual points along X and Y axes, making it ideal for displaying the correlation or distribution of two numerical features."
            },
            {
                "id": 5,
                "question": "What is the primary objective of data cleaning?",
                "options": [
                    "To write code comments",
                    "To identify missing values, handle duplicates, fix formatting, and prepare the dataset for analysis",
                    "To make the files run faster on servers",
                    "To upload the files to GitHub"
                ],
                "correct_index": 1,
                "explanation": "Data cleaning fixes corrupt, incomplete, or incorrectly formatted records before feeding the data into a model."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What does the term 'Imputation' mean in data preprocessing?",
                "options": [
                    "Deleting columns with missing values",
                    "Replacing missing values with estimated values (like mean, median, or predictions)",
                    "Scaling features between 0 and 1",
                    "Encrypting data tables"
                ],
                "correct_index": 1,
                "explanation": "Imputation is the process of replacing missing data with substituted values so that algorithms can process the dataset without errors."
            },
            {
                "id": 2,
                "question": "What is a key difference between L1 (Lasso) and L2 (Ridge) regularization?",
                "options": [
                    "L1 regularization is only for decision trees",
                    "L1 regularization can shrink coefficients to exactly zero, performing feature selection; L2 shrinks them close to zero but not exactly zero",
                    "L2 is faster to execute than L1",
                    "L1 cannot handle continuous target variables"
                ],
                "correct_index": 1,
                "explanation": "Lasso (L1) adds an absolute penalty which can lead to sparse coefficients (feature selection). Ridge (L2) adds a squared penalty, shrinking weights but retaining all variables."
            },
            {
                "id": 3,
                "question": "What is a Confusion Matrix used for?",
                "options": [
                    "To solve encryption algorithm conflicts",
                    "To evaluate the classification performance of a model showing true/false positives and negatives",
                    "To identify memory leaks in Python scripts",
                    "To merge database tables automatically"
                ],
                "correct_index": 1,
                "explanation": "A confusion matrix shows correct and incorrect predictions broken down by class, helping calculate Precision, Recall, and F1-Score."
            },
            {
                "id": 4,
                "question": "What is the main goal of Principal Component Analysis (PCA)?",
                "options": [
                    "To train neural networks faster",
                    "To reduce the dimensionality of a dataset while preserving as much variance as possible",
                    "To split data into train and test sets",
                    "To encrypt column headers for security"
                ],
                "correct_index": 1,
                "explanation": "PCA is an unsupervised technique that projects high-dimensional data onto orthogonal directions of maximum variance."
            },
            {
                "id": 5,
                "question": "In statistical testing, what is the p-value?",
                "options": [
                    "The probability of the model being 100% correct",
                    "The probability of obtaining the observed results (or more extreme) assuming the null hypothesis is true",
                    "The parameter representing the number of folds in cross validation",
                    "The error rate of a classification model"
                ],
                "correct_index": 1,
                "explanation": "A small p-value (typically <= 0.05) indicates strong evidence against the null hypothesis, allowing you to reject it."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "What does the 'Curse of Dimensionality' refer to?",
                "options": [
                    "Slow database loading speeds in big data platforms",
                    "As dimensionality increases, the volume of space grows exponentially, making data points sparse and distance metrics less meaningful",
                    "An error code that happens in neural network layers",
                    "Having too many rows of data in a CSV file"
                ],
                "correct_index": 1,
                "explanation": "In high-dimensional spaces, points become very far apart, and concepts like distance (Euclidean) become ineffective for clustering or classification."
            },
            {
                "id": 2,
                "question": "What is the difference between Bagging and Boosting ensemble methods?",
                "options": [
                    "Bagging models are built sequentially, while Boosting models are built in parallel",
                    "Bagging models are trained in parallel independently, while Boosting models are trained sequentially where each model corrects the errors of its predecessor",
                    "Bagging is only for linear models, while Boosting is for neural networks",
                    "There is no difference; they are synonymous"
                ],
                "correct_index": 1,
                "explanation": "Bagging (like Random Forest) reduces variance by averaging independent models. Boosting (like XGBoost) reduces bias by training sequentially, targeting misclassified instances."
            },
            {
                "id": 3,
                "question": "What is a Random Forest model?",
                "options": [
                    "A single very deep decision tree",
                    "An ensemble of decision trees trained on bootstrapped datasets and random feature subsets",
                    "A neural network architecture that resembles branches",
                    "A sorting algorithm for hierarchical data structures"
                ],
                "correct_index": 1,
                "explanation": "Random Forest is an ensemble classifier consisting of many decision trees, voting on the output class to improve prediction accuracy."
            },
            {
                "id": 4,
                "question": "What is the purpose of K-Fold Cross Validation?",
                "options": [
                    "To multiply the data size K times",
                    "To evaluate model generalizability by partitioning data into K subsets, training K times, and averaging performance",
                    "To run model optimization on K GPU cores",
                    "To cluster the data into K distinct categories"
                ],
                "correct_index": 1,
                "explanation": "K-Fold Cross Validation ensures that every data point is used for both training and testing, reducing evaluation bias."
            },
            {
                "id": 5,
                "question": "What is the F1-Score in binary classification?",
                "options": [
                    "The ratio of true positives to false positives",
                    "The harmonic mean of Precision and Recall, providing a balanced metric for imbalanced classes",
                    "The training speed coefficient of a model",
                    "The accuracy percentage of the model"
                ],
                "correct_index": 1,
                "explanation": "F1-Score balances Precision and Recall, which is crucial when evaluating datasets with highly imbalanced class distributions."
            }
        ]
    },
    "general cs": {
        "beginner": [
            {
                "id": 1,
                "question": "What is an algorithm?",
                "options": [
                    "A programming language compiler",
                    "A step-by-step procedure or set of rules to solve a problem or perform a task",
                    "A database management system",
                    "A graphical user interface design"
                ],
                "correct_index": 1,
                "explanation": "An algorithm is a finite, well-defined sequence of instructions to solve a particular problem."
            },
            {
                "id": 2,
                "question": "Which data structure operates on a Last-In, First-Out (LIFO) basis?",
                "options": ["Queue", "Stack", "Linked List", "Binary Tree"],
                "correct_index": 1,
                "explanation": "A stack is LIFO (elements added last are removed first), whereas a queue is FIFO (First-In, First-Out)."
            },
            {
                "id": 3,
                "question": "What is the time complexity of searching in a sorted array using Binary Search?",
                "options": ["O(1)", "O(n)", "O(log n)", "O(n log n)"],
                "correct_index": 2,
                "explanation": "Binary search divides the search space in half at each step, yielding a logarithmic time complexity O(log n)."
            },
            {
                "id": 4,
                "question": "What does HTML stand for in web technologies?",
                "options": [
                    "HyperText Markup Language",
                    "HighText Machine Language",
                    "Hyperlink Technical Management List",
                    "Home Tool Markup Layout"
                ],
                "correct_index": 0,
                "explanation": "HTML stands for HyperText Markup Language, the standard formatting language for web browsers."
            },
            {
                "id": 5,
                "question": "What is the primary role of a compiler?",
                "options": [
                    "To execute program code line by line",
                    "To translate high-level source code into low-level machine code or bytecode",
                    "To backup code files to cloud storage",
                    "To manage relational databases"
                ],
                "correct_index": 1,
                "explanation": "A compiler translates the entire source code file into executable machine instructions before execution."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What is the average-case time complexity of the QuickSort algorithm?",
                "options": ["O(n)", "O(n^2)", "O(n log n)", "O(log n)"],
                "correct_index": 2,
                "explanation": "QuickSort averages O(n log n) time complexity, though its worst-case is O(n^2) when poor pivots are chosen."
            },
            {
                "id": 2,
                "question": "In object-oriented programming, what is polymorphism?",
                "options": [
                    "The ability to restrict access to class variables",
                    "The capability of different classes to respond to the same message/method in their own unique way",
                    "Creating multiple instances of a class",
                    "Inheriting all variables from a parent class without modification"
                ],
                "correct_index": 1,
                "explanation": "Polymorphism means 'many forms', enabling a single interface to represent different underlying forms (like overriding methods in subclasses)."
            },
            {
                "id": 3,
                "question": "Which data structure uses a hashing function to map keys to values?",
                "options": ["Binary Search Tree", "Hash Table", "Double Ended Queue", "Graph"],
                "correct_index": 1,
                "explanation": "A Hash Table uses a hash function to compute index positions for keys, allowing O(1) average lookup time."
            },
            {
                "id": 4,
                "question": "What is a primary difference between a process and a thread?",
                "options": [
                    "Processes run in parallel, while threads never run in parallel",
                    "Threads share the same memory space of their parent process, whereas processes run in separate memory spaces",
                    "Threads are managed by the database, while processes are managed by the compiler",
                    "Processes do not consume memory, while threads do"
                ],
                "correct_index": 1,
                "explanation": "A thread is a lightweight unit of execution within a process; threads share memory and resources of the process, making inter-thread communication faster but more complex."
            },
            {
                "id": 5,
                "question": "What is the main purpose of Database Normalization?",
                "options": [
                    "To speed up database connection times",
                    "To minimize data redundancy and prevent anomalies by structuring tables logically",
                    "To compress files for smaller storage footprint",
                    "To run analytical reports on large databases"
                ],
                "correct_index": 1,
                "explanation": "Database normalization structures tables to reduce duplicate data (redundancy) and ensure dependency constraints are maintained."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "What does it mean for a problem to be 'NP-complete'?",
                "options": [
                    "It cannot be solved on any standard computer",
                    "It belongs to the class of problems for which no polynomial-time algorithm is known, but any proposed solution can be verified in polynomial time",
                    "It has a constant time complexity O(1)",
                    "It is solved exclusively using neural network models"
                ],
                "correct_index": 1,
                "explanation": "NP-complete problems represent the hardest problems in NP. If a polynomial-time algorithm is found for one, P would equal NP."
            },
            {
                "id": 2,
                "question": "What does the CAP Theorem state for distributed databases?",
                "options": [
                    "A database can never scale horizontally",
                    "A distributed system can guarantee at most two of: Consistency, Availability, and Partition Tolerance",
                    "Transactions must always satisfy ACID properties",
                    "Security, Speed, and Stability cannot coexist"
                ],
                "correct_index": 1,
                "explanation": "CAP states that in the event of a network partition (P), a distributed system must choose between Consistency (C) and Availability (A)."
            },
            {
                "id": 3,
                "question": "In operating systems, what is thrashing?",
                "options": [
                    "A hardware failure in the CPU cache controller",
                    "A condition where the OS spends more time swapping pages in and out of virtual memory than executing actual process instructions",
                    "Removing old log files to clear disk space",
                    "Multiple processes deadlock waiting for print spoolers"
                ],
                "correct_index": 1,
                "explanation": "Thrashing occurs when the OS active working sets exceed physical RAM, causing constant page faults and swapping."
            },
            {
                "id": 4,
                "question": "What is a mutex (mutual exclusion) object used for in multi-threading?",
                "options": [
                    "To speed up CPU clock cycles",
                    "To lock a shared resource so that only one thread can access it at any given time",
                    "To allocate dynamic heap memory",
                    "To compile thread-safe scripts"
                ],
                "correct_index": 1,
                "explanation": "A mutex prevents race conditions by ensuring multiple threads do not access or modify a shared resource simultaneously."
            },
            {
                "id": 5,
                "question": "What did Alan Turing prove with the Halting Problem?",
                "options": [
                    "That all programs will eventually stop executing",
                    "That it is undecidable whether an arbitrary program will halt or run forever on a given input",
                    "That computer speed is limited by thermodynamics",
                    "That compiler errors are unavoidable"
                ],
                "correct_index": 1,
                "explanation": "The Halting Problem is a classic example of an undecidable decision problem in computability theory, proving absolute mathematical limits of computers."
            }
        ]
    }
}

def get_local_fallback_questions(track, skill_level):
    track_key = track.lower() if track else 'general cs'
    level_key = skill_level.lower() if skill_level else 'beginner'
    
    # Normalizer
    if 'artificial' in track_key or 'ai' in track_key or 'machine' in track_key:
        track_key = 'artificial intelligence'
    elif 'web' in track_key or 'frontend' in track_key or 'backend' in track_key or 'full-stack' in track_key:
        track_key = 'web development'
    elif 'data' in track_key or 'science' in track_key or 'analytics' in track_key:
        track_key = 'data science'
    else:
        track_key = 'general cs'
        
    if level_key not in ['beginner', 'intermediate', 'advanced']:
        level_key = 'beginner'
        
    track_bank = LOCAL_QUIZ_BANK.get(track_key, LOCAL_QUIZ_BANK['general cs'])
    return track_bank.get(level_key, track_bank['beginner'])

