# book-graph
Generates a similarity network for a book based on tags queried from Open Library's Search API

As someone who is quite picky about what they read, searching for my next book can often be a time consuming task. 
My goal with this project was to help myself and others narrow in on specific aspects of books they enjoy, and find reads that share in that aspect. 

For example, if you just read Girl with a Pearl Earring by Tracy Chevalier, and found that having a main character who is an artist is a fascinating perspective, the book-graph will retrieve books whose plots revolve around that of an artist (among other important characteristics of the book).

As of now, its output is too generalized to be useful. If you have a book tagged as "fiction", it will generate generic suggestions, with little regard to the content of the original input.
Not only that, but it actually suggests literal works of art - not particularly useful if you're in the mood for reading.

Currently working on improving output and functionality. As of now, it is about 10% complete. 
